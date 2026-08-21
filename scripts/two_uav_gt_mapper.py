#!/usr/bin/env python3
"""Two-vehicle GT synchronized registration adapter for the frozen 20 m baseline."""

import math

import numpy as np


MIN_RANGE_M = 0.5
MAX_RANGE_M = 20.0
SYNC_SLOP_S = 0.05
DOWNSAMPLE_STRIDE = 3


def filter_and_decimate_points(raw, min_range_m=MIN_RANGE_M,
                               max_range_m=MAX_RANGE_M,
                               stride=DOWNSAMPLE_STRIDE):
    points = np.asarray(raw, dtype=np.float32).reshape((-1, 3))
    if min_range_m < 0.0 or max_range_m <= min_range_m:
        raise ValueError("expected 0 <= min_range_m < max_range_m")
    if stride < 1:
        raise ValueError("stride must be >= 1")
    if points.size == 0:
        return points, {"nonfinite": 0, "near": 0, "far": 0}
    finite = np.isfinite(points).all(axis=1)
    ranges = np.linalg.norm(points, axis=1)
    near = finite & (ranges < min_range_m)
    far = finite & (ranges > max_range_m)
    accepted = points[finite & ~near & ~far]
    return accepted[::stride], {
        "nonfinite": int((~finite).sum()),
        "near": int(near.sum()),
        "far": int(far.sum()),
    }


def rotation_from_quaternion(values):
    x, y, z, w = values
    norm = x * x + y * y + z * z + w * w
    if norm < 1e-12:
        return np.eye(3, dtype=np.float32)
    scale = 2.0 / norm
    xx, yy, zz = x * x * scale, y * y * scale, z * z * scale
    xy, xz, yz = x * y * scale, x * z * scale, y * z * scale
    wx, wy, wz = w * x * scale, w * y * scale, w * z * scale
    return np.asarray([
        [1.0 - yy - zz, xy - wz, xz + wy],
        [xy + wz, 1.0 - xx - zz, yz - wx],
        [xz - wy, yz + wx, 1.0 - xx - yy],
    ], dtype=np.float32)


def register_points(points, quaternion, local_position, initial_position):
    rotation = rotation_from_quaternion(quaternion)
    sensor_offset = np.asarray([0.0, 0.0, 0.13], dtype=np.float32)
    translated = (points + sensor_offset).dot(rotation.T)
    translated += np.asarray(local_position, dtype=np.float32)
    translated += np.asarray(initial_position, dtype=np.float32)
    return translated


def world_base_transform(child_frame, stamp, position, orientation):
    """Pure contract for the sole world -> uavN/base_link transform."""
    return {"parent": "world", "child": child_frame, "stamp": stamp,
            "translation": tuple(position), "rotation": tuple(orientation)}


class VehicleMapper:
    def __init__(self, spec):
        import message_filters
        import rospy
        from nav_msgs.msg import Odometry
        from sensor_msgs.msg import PointCloud, PointCloud2
        from geometry_msgs.msg import PoseStamped, TransformStamped
        import tf2_ros

        self._rospy = rospy
        self._spec = spec
        self._initial = spec["initial_position"]
        self._child_frame = spec["frames"]["child"]
        topics = spec["topics"]
        self._cloud_pub = rospy.Publisher(
            topics["registered_cloud"], PointCloud2, queue_size=2)
        self._odom_pub = rospy.Publisher(
            topics["registered_odom"], Odometry, queue_size=10)
        self._pose_pub = rospy.Publisher(
            topics["registered_pose"], PoseStamped, queue_size=10)
        self._tf_pub = tf2_ros.TransformBroadcaster()
        scan_sub = message_filters.Subscriber(
            topics["raw_cloud"], PointCloud, queue_size=20)
        odom_sub = message_filters.Subscriber(
            topics["mavros_odom"], Odometry, queue_size=50)
        self._sync = message_filters.ApproximateTimeSynchronizer(
            [scan_sub, odom_sub], queue_size=100, slop=SYNC_SLOP_S,
            allow_headerless=False)
        self._sync.registerCallback(self._callback)
        self._scans = 0
        self._input_counts = {"scan": 0, "odom": 0, "pairs": 0,
                              "empty_scan": 0, "empty_filtered": 0}
        scan_sub.registerCallback(self._input_cb, "scan")
        odom_sub.registerCallback(self._input_cb, "odom")
        rospy.Timer(rospy.Duration(10.0), self._diagnostics)

    def _input_cb(self, _message, name):
        self._input_counts[name] += 1

    def _diagnostics(self, _event):
        self._rospy.loginfo("%s mapper inputs=%s outputs=%d",
                            self._spec["name"], self._input_counts, self._scans)

    def _callback(self, scan, odom):
        from geometry_msgs.msg import PoseStamped, TransformStamped
        from nav_msgs.msg import Odometry
        from sensor_msgs import point_cloud2
        from std_msgs.msg import Header

        self._input_counts["pairs"] += 1
        if not scan.points:
            self._input_counts["empty_scan"] += 1
            return
        raw = [(point.x, point.y, point.z) for point in scan.points]
        points, _counts = filter_and_decimate_points(raw)
        if points.size == 0:
            self._input_counts["empty_filtered"] += 1
            return
        pose = odom.pose.pose
        world = register_points(
            points,
            (pose.orientation.x, pose.orientation.y,
             pose.orientation.z, pose.orientation.w),
            (pose.position.x, pose.position.y, pose.position.z),
            self._initial)
        header = Header(seq=scan.header.seq, stamp=scan.header.stamp,
                        frame_id="world")
        out_odom = Odometry()
        out_odom.header = header
        out_odom.child_frame_id = self._child_frame
        out_odom.pose = odom.pose
        out_odom.pose.pose.position.x += self._initial[0]
        out_odom.pose.pose.position.y += self._initial[1]
        out_odom.pose.pose.position.z += self._initial[2]
        out_odom.twist = odom.twist
        out_pose = PoseStamped(header=header, pose=out_odom.pose.pose)
        self._cloud_pub.publish(
            point_cloud2.create_cloud_xyz32(header, world.tolist()))
        self._odom_pub.publish(out_odom)
        self._pose_pub.publish(out_pose)
        transform = world_base_transform(
            self._child_frame, header.stamp,
            (out_odom.pose.pose.position.x, out_odom.pose.pose.position.y,
             out_odom.pose.pose.position.z),
            (out_odom.pose.pose.orientation.x, out_odom.pose.pose.orientation.y,
             out_odom.pose.pose.orientation.z, out_odom.pose.pose.orientation.w))
        tf_message = TransformStamped()
        tf_message.header.stamp = transform["stamp"]
        tf_message.header.frame_id = transform["parent"]
        tf_message.child_frame_id = transform["child"]
        tf_message.transform.translation.x, tf_message.transform.translation.y, tf_message.transform.translation.z = transform["translation"]
        tf_message.transform.rotation.x, tf_message.transform.rotation.y, tf_message.transform.rotation.z, tf_message.transform.rotation.w = transform["rotation"]
        self._tf_pub.sendTransform(tf_message)
        self._scans += 1
        self._rospy.loginfo_throttle(
            10.0, "%s registered scans=%d", self._spec["name"], self._scans)


def load_contract(path):
    import yaml
    with open(path, encoding="utf-8") as stream:
        contract = yaml.safe_load(stream)
    if contract.get("registration_source") != "gt":
        raise ValueError("GT mapper refuses non-GT registration contract")
    if contract.get("uav_count") != 2 or len(contract.get("vehicles", [])) != 2:
        raise ValueError("GT mapper requires exactly two vehicles")
    return contract


def self_test():
    raw = [[0.1, 0.0, 0.0], [1.0, 0.0, 0.0],
           [21.0, 0.0, 0.0], [math.nan, 0.0, 0.0]]
    filtered, counts = filter_and_decimate_points(raw, stride=1)
    assert filtered.shape == (1, 3)
    assert counts == {"nonfinite": 1, "near": 1, "far": 1}
    registered = register_points(
        filtered, (0.0, 0.0, 0.0, 1.0), (0.0, 0.0, 1.0),
        (1.5, 0.0, 0.0))
    assert np.allclose(registered[0], [2.5, 0.0, 1.13])
    uav0 = world_base_transform("uav0/base_link", 42, (1.0, 2.0, 3.0),
                                (0.0, 0.0, 0.0, 1.0))
    uav1 = world_base_transform("uav1/base_link", 42, (-1.0, 4.0, 2.0),
                                (0.0, 0.0, 1.0, 0.0))
    assert {uav0["parent"], uav1["parent"]} == {"world"}
    assert {uav0["child"], uav1["child"]} == {"uav0/base_link", "uav1/base_link"}
    assert uav0["stamp"] == uav1["stamp"] == 42
    assert uav0["translation"] == (1.0, 2.0, 3.0)
    assert uav1["translation"] == (-1.0, 4.0, 2.0)
    assert uav0["rotation"] == (0.0, 0.0, 0.0, 1.0)
    assert uav1["rotation"] == (0.0, 0.0, 1.0, 0.0)
    print("two_uav_gt_mapper self-test: PASS")


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="config/2uav_static.yaml")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        self_test()
        return
    import rospy
    rospy.init_node("two_uav_gt_mapper", anonymous=False)
    contract = load_contract(args.config)
    mappers = [VehicleMapper(spec) for spec in contract["vehicles"]]
    rospy.loginfo("two_uav_gt_mapper ready for %s",
                  ", ".join(mapper._spec["name"] for mapper in mappers))
    rospy.spin()


if __name__ == "__main__":
    main()
