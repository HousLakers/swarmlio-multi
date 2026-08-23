#!/usr/bin/env python3
"""Two-vehicle GT synchronized registration adapter for the frozen 20 m baseline."""

import copy
import json
import math
from pathlib import Path
import threading

import numpy as np


MIN_RANGE_M = 0.5
MAX_RANGE_M = 20.0
SYNC_SLOP_S = 0.05
DOWNSAMPLE_STRIDE = 3
LIDAR_SENSOR_OFFSET_M = (0.0, 0.0, 0.13)
# Frozen static-contract values used only by the provenance recorder.  They do
# not participate in registration, peer masking, publishing, or control.
OCCUPANCY_VOXEL_M = 0.25
OCCUPANCY_INFLATION_M = 0.35
UAV1_HOVER_WORLD = (1.5, 0.0, 1.5)
# Frozen collision identity: iris.sdf.jinja@e8ae6d24..., collision primitives
# base_link_inertia_collision, rotor_[0-3]_collision and link_platform/collision.
IRIS_COLLISION_GEOMETRY_ID = "iris.sdf.jinja:e8ae6d24c7d85124326db2f795aa72286772da3520110419919a897527d73225"
IRIS_COLLISION_PRIMITIVES = (
    ("box", (0.0, 0.0, 0.0), (0.47, 0.47, 0.11)),
    ("cylinder", (0.13, -0.22, 0.023), (0.128, 0.005)),
    ("cylinder", (-0.13, 0.2, 0.023), (0.128, 0.005)),
    ("cylinder", (0.13, 0.22, 0.023), (0.128, 0.005)),
    ("cylinder", (-0.13, -0.2, 0.023), (0.128, 0.005)),
    ("box", (0.0, 0.0, 0.05), (0.15, 0.1, 0.1)),
)


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
    translated = (points + np.asarray(LIDAR_SENSOR_OFFSET_M, dtype=np.float32)).dot(rotation.T)
    translated += np.asarray(local_position, dtype=np.float32)
    translated += np.asarray(initial_position, dtype=np.float32)
    return translated


def lidar_sensor_world_origin(quaternion, local_position, initial_position):
    """Return the frozen LiDAR origin used by ``register_points()``."""
    rotation = rotation_from_quaternion(quaternion)
    body_world = (np.asarray(local_position, dtype=np.float32) +
                  np.asarray(initial_position, dtype=np.float32))
    return (np.asarray(LIDAR_SENSOR_OFFSET_M, dtype=np.float32).dot(rotation.T) +
            body_world)


def world_base_transform(child_frame, stamp, position, orientation):
    """Pure contract for the sole world -> uavN/base_link transform."""
    return {"parent": "world", "child": child_frame, "stamp": stamp,
            "translation": tuple(position), "rotation": tuple(orientation)}


def stamp_seconds(stamp):
    if isinstance(stamp, (int, float)) and not isinstance(stamp, bool):
        value = float(stamp)
    elif hasattr(stamp, "to_sec"):
        value = float(stamp.to_sec())
    elif hasattr(stamp, "secs") and hasattr(stamp, "nsecs"):
        value = float(stamp.secs) + float(stamp.nsecs) * 1e-9
    else:
        return None
    return value if math.isfinite(value) else None


def pose_record(stamp, position, orientation):
    """Build a finite, immutable world-pose record for diagnostic classification."""
    stamp = stamp_seconds(stamp)
    position = tuple(float(value) for value in position)
    orientation = tuple(float(value) for value in orientation)
    if (stamp is None or len(position) != 3 or len(orientation) != 4 or
            not all(math.isfinite(value) for value in position + orientation) or
            sum(value * value for value in orientation) < 1e-12):
        return None
    return {"stamp": stamp, "position": position, "orientation": orientation}


def pose_freshness(pose, sample_stamp, max_delta_s=SYNC_SLOP_S):
    if pose is None:
        return "missing"
    sample_stamp = stamp_seconds(sample_stamp)
    if sample_stamp is None:
        return "uncomparable"
    if abs(sample_stamp - pose["stamp"]) > max_delta_s:
        return "stale"
    return "available"


def points_in_iris_collision_envelope(world_points, pose):
    """Return the exact frozen-collision candidate mask; never mutate *world_points*."""
    points = np.asarray(world_points, dtype=np.float32).reshape((-1, 3))
    mask = np.zeros(len(points), dtype=bool)
    if pose is None or points.size == 0:
        return mask
    rotation = rotation_from_quaternion(pose["orientation"])
    local = (points - np.asarray(pose["position"], dtype=np.float32)).dot(rotation)
    finite = np.isfinite(local).all(axis=1)
    for kind, center, dimensions in IRIS_COLLISION_PRIMITIVES:
        delta = local - np.asarray(center, dtype=np.float32)
        if kind == "box":
            inside = np.all(np.abs(delta) <= np.asarray(dimensions, dtype=np.float32) / 2.0,
                            axis=1)
        else:
            radius, length = dimensions
            inside = ((delta[:, 0] * delta[:, 0] + delta[:, 1] * delta[:, 1] <= radius * radius) &
                      (np.abs(delta[:, 2]) <= length / 2.0))
        mask |= finite & inside
    return mask


def _segment_intersects_box_local(origin, endpoints, center, dimensions):
    """Return closed-segment intersections with one frozen local box."""
    direction = endpoints - origin
    lower = np.asarray(center, dtype=np.float64) - (
        np.asarray(dimensions, dtype=np.float64) / 2.0)
    upper = np.asarray(center, dtype=np.float64) + (
        np.asarray(dimensions, dtype=np.float64) / 2.0)
    start = np.broadcast_to(origin, endpoints.shape)
    entry = np.zeros(len(endpoints), dtype=np.float64)
    exit_ = np.ones(len(endpoints), dtype=np.float64)
    valid = np.isfinite(endpoints).all(axis=1) & np.isfinite(origin).all()
    for axis in range(3):
        parallel = direction[:, axis] == 0.0
        valid &= ~parallel | ((start[:, axis] >= lower[axis]) &
                              (start[:, axis] <= upper[axis]))
        nonparallel = ~parallel
        first = np.zeros(len(endpoints), dtype=np.float64)
        second = np.ones(len(endpoints), dtype=np.float64)
        first[nonparallel] = ((lower[axis] - start[nonparallel, axis]) /
                              direction[nonparallel, axis])
        second[nonparallel] = ((upper[axis] - start[nonparallel, axis]) /
                               direction[nonparallel, axis])
        entry = np.maximum(entry, np.minimum(first, second))
        exit_ = np.minimum(exit_, np.maximum(first, second))
    return valid & (entry <= exit_)


def _segment_intersects_cylinder_local(origin, endpoints, center, dimensions):
    """Return closed-segment intersections with one frozen local z-cylinder."""
    direction = endpoints - origin
    center = np.asarray(center, dtype=np.float64)
    radius, length = dimensions
    start = np.broadcast_to(origin, endpoints.shape) - center
    direction = np.asarray(direction, dtype=np.float64)
    valid = np.isfinite(endpoints).all(axis=1) & np.isfinite(origin).all()

    z_entry = np.zeros(len(endpoints), dtype=np.float64)
    z_exit = np.ones(len(endpoints), dtype=np.float64)
    half_length = length / 2.0
    parallel_z = direction[:, 2] == 0.0
    valid &= ~parallel_z | ((start[:, 2] >= -half_length) &
                            (start[:, 2] <= half_length))
    nonparallel_z = ~parallel_z
    z_first = np.zeros(len(endpoints), dtype=np.float64)
    z_second = np.ones(len(endpoints), dtype=np.float64)
    z_first[nonparallel_z] = ((-half_length - start[nonparallel_z, 2]) /
                              direction[nonparallel_z, 2])
    z_second[nonparallel_z] = ((half_length - start[nonparallel_z, 2]) /
                               direction[nonparallel_z, 2])
    z_entry = np.maximum(z_entry, np.minimum(z_first, z_second))
    z_exit = np.minimum(z_exit, np.maximum(z_first, z_second))

    radial_a = direction[:, 0] ** 2 + direction[:, 1] ** 2
    radial_b = 2.0 * (start[:, 0] * direction[:, 0] +
                      start[:, 1] * direction[:, 1])
    radial_c = start[:, 0] ** 2 + start[:, 1] ** 2 - radius * radius
    radial_entry = np.zeros(len(endpoints), dtype=np.float64)
    radial_exit = np.ones(len(endpoints), dtype=np.float64)
    parallel_radial = radial_a == 0.0
    valid &= ~parallel_radial | (radial_c <= 0.0)
    nonparallel_radial = ~parallel_radial
    discriminant = radial_b ** 2 - 4.0 * radial_a * radial_c
    valid &= ~nonparallel_radial | (discriminant >= 0.0)
    roots = np.zeros(len(endpoints), dtype=np.float64)
    root_ok = nonparallel_radial & (discriminant >= 0.0)
    roots[root_ok] = np.sqrt(discriminant[root_ok])
    radial_first = np.zeros(len(endpoints), dtype=np.float64)
    radial_second = np.ones(len(endpoints), dtype=np.float64)
    radial_first[root_ok] = ((-radial_b[root_ok] - roots[root_ok]) /
                             (2.0 * radial_a[root_ok]))
    radial_second[root_ok] = ((-radial_b[root_ok] + roots[root_ok]) /
                              (2.0 * radial_a[root_ok]))
    radial_entry = np.maximum(radial_entry, np.minimum(radial_first, radial_second))
    radial_exit = np.minimum(radial_exit, np.maximum(radial_first, radial_second))
    return valid & (np.maximum(z_entry, radial_entry) <= np.minimum(z_exit, radial_exit))


def peer_ray_intersection_mask(world_points, source_pose, peer_pose):
    """Mask endpoints whose closed source ray exactly crosses a peer primitive."""
    points = np.asarray(world_points, dtype=np.float32).reshape((-1, 3))
    mask = np.zeros(len(points), dtype=bool)
    if source_pose is None or peer_pose is None or points.size == 0:
        return mask
    rotation = rotation_from_quaternion(peer_pose["orientation"])
    peer_position = np.asarray(peer_pose["position"], dtype=np.float32)
    origin = (np.asarray(source_pose["position"], dtype=np.float32) -
              peer_position).dot(rotation).astype(np.float64)
    endpoints = ((points - peer_position).dot(rotation)).astype(np.float64)
    for kind, center, dimensions in IRIS_COLLISION_PRIMITIVES:
        if kind == "box":
            mask |= _segment_intersects_box_local(origin, endpoints, center, dimensions)
        else:
            mask |= _segment_intersects_cylinder_local(origin, endpoints, center, dimensions)
    return mask


def points_in_iris_inflation_neighborhood(world_points, pose,
                                          inflation_m=OCCUPANCY_INFLATION_M):
    """Return the frozen exact-distance collision inflation-neighborhood mask."""
    points = np.asarray(world_points, dtype=np.float32).reshape((-1, 3))
    if inflation_m < 0.0:
        raise ValueError("inflation_m must be non-negative")
    mask = np.zeros(len(points), dtype=bool)
    if pose is None or points.size == 0:
        return mask
    rotation = rotation_from_quaternion(pose["orientation"])
    local = (points - np.asarray(pose["position"], dtype=np.float32)).dot(rotation)
    finite = np.isfinite(local).all(axis=1)
    for kind, center, dimensions in IRIS_COLLISION_PRIMITIVES:
        delta = local - np.asarray(center, dtype=np.float32)
        if kind == "box":
            outside = np.maximum(np.abs(delta) -
                                 np.asarray(dimensions, dtype=np.float32) / 2.0, 0.0)
            distance = np.linalg.norm(outside, axis=1)
        else:
            radius, length = dimensions
            radial = np.maximum(np.hypot(delta[:, 0], delta[:, 1]) - radius, 0.0)
            axial = np.maximum(np.abs(delta[:, 2]) - length / 2.0, 0.0)
            distance = np.hypot(radial, axial)
        mask |= finite & (distance <= inflation_m)
    return mask


def hover_neighborhood_voxels(world_points, sim_stamp,
                               hover_world=UAV1_HOVER_WORLD,
                               neighborhood_m=OCCUPANCY_INFLATION_M,
                               voxel_m=OCCUPANCY_VOXEL_M):
    """Return observed hover-neighborhood voxels without modifying points."""
    points = np.asarray(world_points, dtype=np.float32).reshape((-1, 3))
    stamp = stamp_seconds(sim_stamp)
    if stamp is None or neighborhood_m < 0.0 or voxel_m <= 0.0:
        return {}
    delta = points - np.asarray(hover_world, dtype=np.float32)
    selected = np.isfinite(points).all(axis=1) & (
        np.linalg.norm(delta, axis=1) <= neighborhood_m)
    voxels = {}
    for point in points[selected]:
        key = ",".join(str(int(value)) for value in np.floor(point / voxel_m))
        voxels[key] = voxels.get(key, 0) + 1
    return voxels


def record_provenance_diagnostic(counts, published_points, source_name, sample_stamp,
                                 peer_pose, peer_status):
    """Mutate only *counts* with audit data; return no point-cloud data.

    Hover voxels deliberately derive from the exact published array.  The
    ``peer_unavailable_*`` fields are reserved for stale/missing/uncomparable
    classifications; an available pose must never enter them.
    """
    stamp = stamp_seconds(sample_stamp)
    for voxel, hits in hover_neighborhood_voxels(published_points, stamp).items():
        record = counts["uav1_hover_voxels"].setdefault(
            voxel, {"source_uav": source_name, "point_hits": 0,
                    "first_sim_time": stamp, "recent_sim_time": stamp})
        record["point_hits"] += hits
        record["recent_sim_time"] = stamp
    if peer_status not in {"stale", "missing", "uncomparable"}:
        return
    statuses = counts["peer_unavailable_pose_status"]
    statuses[peer_status] = statuses.get(peer_status, 0) + 1
    if peer_pose is None:
        return
    body = points_in_iris_collision_envelope(published_points, peer_pose)
    inflated = points_in_iris_inflation_neighborhood(published_points, peer_pose)
    counts["peer_unavailable_body_candidates"] += int(body.sum())
    counts["peer_unavailable_inflation_candidates"] += int(inflated.sum())


def classify_body_candidates(world_points, source_name, peer_name, sample_stamp, poses):
    """Return audit counts from the same peer-only filter decision used at runtime."""
    _published, result = peer_body_filter(
        world_points, source_name, peer_name, sample_stamp, poses)
    return {
        key: result[key] for key in (
            "registered_points", "self_candidates", "peer_candidates",
            "self_pose_status", "peer_pose_status")
    }


def multi_peer_body_filter(world_points, source_name, peer_names, sample_stamp, poses,
                           source_scan_pose=None):
    """Remove points colliding with ANY available peer pose.

    For a single peer this matches peer_body_filter (same points, same
    diagnostic keys and counts); with N>1 peers the endpoint/inflation/ray
    candidate masks are summed and unioned before removal.
    """
    if isinstance(peer_names, str):
        peer_names = [peer_names]
    source_pose = poses.get(source_name)
    ray_source_pose = source_scan_pose or source_pose
    source_status = pose_freshness(source_pose, sample_stamp)
    ray_source_status = pose_freshness(ray_source_pose, sample_stamp)
    points = np.asarray(world_points, dtype=np.float32).reshape((-1, 3))
    self_candidates = int(points_in_iris_collision_envelope(
        points, source_pose).sum()) if source_status == "available" else 0
    endpoint_candidates = 0
    inflation_candidates = 0
    ray_candidates = 0
    removed_mask = np.zeros(len(points), dtype=bool)
    any_available = False
    first_status = None
    for peer_name in peer_names:
        peer_status = pose_freshness(poses.get(peer_name), sample_stamp)
        first_status = first_status or peer_status
        if peer_status != "available":
            continue
        any_available = True
        peer_pose = poses[peer_name]
        endpoint_mask = points_in_iris_collision_envelope(points, peer_pose)
        inflation_endpoint_mask = points_in_iris_inflation_neighborhood(points, peer_pose)
        ray_mask = (peer_ray_intersection_mask(points, ray_source_pose, peer_pose)
                    if ray_source_status == "available" else np.zeros(len(points), dtype=bool))
        endpoint_candidates += int(endpoint_mask.sum())
        inflation_candidates += int(inflation_endpoint_mask.sum())
        ray_candidates += int(ray_mask.sum())
        removed_mask |= endpoint_mask | inflation_endpoint_mask | ray_mask
    if not any_available:
        return points, {
            "registered_points": int(len(points)),
            "published_points": int(len(points)),
            "self_candidates": self_candidates,
            "peer_candidates": 0,
            "peer_endpoint_candidates": 0,
            "peer_inflation_endpoint_candidates": 0,
            "peer_ray_candidates": 0,
            "peer_removed_points": 0,
            "peer_preserved_unavailable_points": int(len(points)),
            "self_pose_status": source_status,
            "ray_source_pose_status": ray_source_status,
            "peer_pose_status": first_status or "missing",
        }
    removed_points = int(removed_mask.sum())
    return points[~removed_mask], {
        "registered_points": int(len(points)),
        "published_points": int(len(points) - removed_points),
        "self_candidates": self_candidates,
        "peer_candidates": endpoint_candidates,
        "peer_endpoint_candidates": endpoint_candidates,
        "peer_inflation_endpoint_candidates": inflation_candidates,
        "peer_ray_candidates": ray_candidates,
        "peer_removed_points": removed_points,
        "peer_preserved_unavailable_points": 0,
        "self_pose_status": source_status,
        "ray_source_pose_status": ray_source_status,
        "peer_pose_status": "available",
    }


def peer_body_filter(world_points, source_name, peer_name, sample_stamp, poses,
                     source_scan_pose=None):
    """Remove only exact endpoint/ray peer collisions with an available peer pose."""
    source_pose = poses.get(source_name)
    ray_source_pose = source_scan_pose or source_pose
    peer_pose = poses.get(peer_name)
    source_status = pose_freshness(source_pose, sample_stamp)
    ray_source_status = pose_freshness(ray_source_pose, sample_stamp)
    peer_status = pose_freshness(peer_pose, sample_stamp)
    points = np.asarray(world_points, dtype=np.float32).reshape((-1, 3))
    self_candidates = int(points_in_iris_collision_envelope(
        points, source_pose).sum()) if source_status == "available" else 0
    if peer_status != "available":
        return points, {
            "registered_points": int(len(points)),
            "published_points": int(len(points)),
            "self_candidates": self_candidates,
            "peer_candidates": 0,
            "peer_endpoint_candidates": 0,
            "peer_inflation_endpoint_candidates": 0,
            "peer_ray_candidates": 0,
            "peer_removed_points": 0,
            "peer_preserved_unavailable_points": int(len(points)),
            "self_pose_status": source_status,
            "ray_source_pose_status": ray_source_status,
            "peer_pose_status": peer_status,
        }
    endpoint_mask = points_in_iris_collision_envelope(points, peer_pose)
    inflation_endpoint_mask = points_in_iris_inflation_neighborhood(
        points, peer_pose)
    ray_mask = (peer_ray_intersection_mask(points, ray_source_pose, peer_pose)
                if ray_source_status == "available" else np.zeros(len(points), dtype=bool))
    removed_mask = endpoint_mask | inflation_endpoint_mask | ray_mask
    endpoint_candidates = int(endpoint_mask.sum())
    inflation_endpoint_candidates = int(inflation_endpoint_mask.sum())
    ray_candidates = int(ray_mask.sum())
    removed_points = int(removed_mask.sum())
    return points[~removed_mask], {
        "registered_points": int(len(points)),
        "published_points": int(len(points) - removed_points),
        "self_candidates": self_candidates,
        # Retained for prior diagnostic consumers; it means endpoint candidates.
        "peer_candidates": endpoint_candidates,
        "peer_endpoint_candidates": endpoint_candidates,
        "peer_inflation_endpoint_candidates": inflation_endpoint_candidates,
        "peer_ray_candidates": ray_candidates,
        "peer_removed_points": removed_points,
        "peer_preserved_unavailable_points": 0,
        "self_pose_status": source_status,
        "ray_source_pose_status": ray_source_status,
        "peer_pose_status": peer_status,
    }


class PoseLedger:
    """Thread-safe latest MAVROS-odom world poses shared by both mappers."""
    def __init__(self):
        self._lock = threading.Lock()
        self._poses = {}

    def update(self, name, stamp, position, orientation):
        record = pose_record(stamp, position, orientation)
        if record is None:
            return False
        with self._lock:
            previous = self._poses.get(name)
            if previous is not None and record["stamp"] < previous["stamp"]:
                return False
            self._poses[name] = record
        return True

    def snapshot(self):
        with self._lock:
            return dict(self._poses)


def body_diagnostic_snapshot(body_counts, source, peer):
    """Return a detached, JSON-ready audit record for one mapper source."""
    snapshot = copy.deepcopy(body_counts)
    snapshot["geometry_id"] = IRIS_COLLISION_GEOMETRY_ID
    snapshot["source"] = source
    snapshot["peer"] = peer
    return snapshot


def offset_pose_copy(pose_with_covariance, initial_position):
    """Return a detached registered pose without mutating the MAVROS input."""
    result = copy.deepcopy(pose_with_covariance)
    result.pose.position.x += initial_position[0]
    result.pose.position.y += initial_position[1]
    result.pose.position.z += initial_position[2]
    return result


class VehicleMapper:
    def __init__(self, spec, pose_ledger, peer_names):
        import message_filters
        import rospy
        from nav_msgs.msg import Odometry
        from sensor_msgs.msg import PointCloud, PointCloud2
        from geometry_msgs.msg import PoseStamped, TransformStamped
        import tf2_ros

        if isinstance(peer_names, str):
            peer_names = (peer_names,)
        self._rospy = rospy
        self._spec = spec
        self._pose_ledger = pose_ledger
        self._peer_names = tuple(peer_names)
        self._peer_name = self._peer_names[0] if self._peer_names else None
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
        self._body_counts = {"raw_points": 0, "registered_points": 0,
                             "published_points": 0, "self_candidates": 0,
                             "peer_candidates": 0, "peer_endpoint_candidates": 0,
                             "peer_inflation_endpoint_candidates": 0,
                             "peer_ray_candidates": 0, "peer_removed_points": 0,
                             "peer_preserved_unavailable_points": 0,
                             "self_pose_status": {}, "ray_source_pose_status": {},
                             "peer_pose_status": {},
                             "uav1_hover_voxels": {},
                             "peer_unavailable_body_candidates": 0,
                             "peer_unavailable_inflation_candidates": 0,
                             "peer_unavailable_pose_status": {}}
        self._body_lock = threading.Lock()
        scan_sub.registerCallback(self._input_cb, "scan")
        odom_sub.registerCallback(self._input_cb, "odom")
        odom_sub.registerCallback(self._odom_pose_cb)
        rospy.Timer(rospy.Duration(10.0), self._diagnostics)

    def _input_cb(self, _message, name):
        self._input_counts[name] += 1

    def _odom_pose_cb(self, odom):
        pose = odom.pose.pose
        self._pose_ledger.update(
            self._spec["name"], odom.header.stamp,
            (pose.position.x + self._initial[0], pose.position.y + self._initial[1],
             pose.position.z + self._initial[2]),
            (pose.orientation.x, pose.orientation.y,
             pose.orientation.z, pose.orientation.w))

    def _diagnostics(self, _event):
        self._rospy.loginfo("%s mapper inputs=%s outputs=%d",
                            self._spec["name"], self._input_counts, self._scans)
        with self._body_lock:
            body = body_diagnostic_snapshot(
                self._body_counts, self._spec["name"], self._peer_name)
        self._rospy.loginfo("mapper_body_diagnostic=%s",
                            json.dumps(body, sort_keys=True, separators=(",", ":")))

    def _record_body_diagnostics(self, result):
        with self._body_lock:
            self._body_counts["registered_points"] += result["registered_points"]
            self._body_counts["published_points"] += result["published_points"]
            self._body_counts["self_candidates"] += result["self_candidates"]
            self._body_counts["peer_candidates"] += result["peer_candidates"]
            self._body_counts["peer_endpoint_candidates"] += result["peer_endpoint_candidates"]
            self._body_counts["peer_inflation_endpoint_candidates"] += result[
                "peer_inflation_endpoint_candidates"]
            self._body_counts["peer_ray_candidates"] += result["peer_ray_candidates"]
            self._body_counts["peer_removed_points"] += result["peer_removed_points"]
            self._body_counts["peer_preserved_unavailable_points"] += result[
                "peer_preserved_unavailable_points"]
            for key in ("self_pose_status", "ray_source_pose_status", "peer_pose_status"):
                status = result[key]
                statuses = self._body_counts[key]
                statuses[status] = statuses.get(status, 0) + 1

    def _record_provenance_diagnostics(self, published, scan_stamp, poses, result):
        """Record read-only provenance from the existing publication result."""
        with self._body_lock:
            record_provenance_diagnostic(
                self._body_counts, published, self._spec["name"], scan_stamp,
                poses.get(self._peer_name), result["peer_pose_status"])

    def _callback(self, scan, odom):
        from geometry_msgs.msg import PoseStamped, TransformStamped
        from nav_msgs.msg import Odometry
        from sensor_msgs import point_cloud2
        from std_msgs.msg import Header

        self._input_counts["pairs"] += 1
        pose = odom.pose.pose
        scan_stamp = stamp_seconds(scan.header.stamp)
        orientation = (pose.orientation.x, pose.orientation.y,
                       pose.orientation.z, pose.orientation.w)
        if not scan.points:
            self._input_counts["empty_scan"] += 1
            return
        raw = [(point.x, point.y, point.z) for point in scan.points]
        with self._body_lock:
            self._body_counts["raw_points"] += len(raw)
        points, _counts = filter_and_decimate_points(raw)
        if points.size == 0:
            self._input_counts["empty_filtered"] += 1
            return
        world = register_points(
            points,
            orientation,
            (pose.position.x, pose.position.y, pose.position.z),
            self._initial)
        source_scan_pose = pose_record(
            scan.header.stamp,
            lidar_sensor_world_origin(
                orientation,
                (pose.position.x, pose.position.y, pose.position.z), self._initial),
            orientation)
        poses = self._pose_ledger.snapshot()
        published, body_result = multi_peer_body_filter(
            world, self._spec["name"], self._peer_names, scan_stamp, poses,
            source_scan_pose=source_scan_pose)
        self._record_provenance_diagnostics(
            published, scan_stamp, poses, body_result)
        self._record_body_diagnostics(body_result)
        header = Header(seq=scan.header.seq, stamp=scan.header.stamp,
                        frame_id="world")
        out_odom = Odometry()
        out_odom.header = header
        out_odom.child_frame_id = self._child_frame
        out_odom.pose = offset_pose_copy(odom.pose, self._initial)
        out_odom.twist = odom.twist
        out_pose = PoseStamped(header=header, pose=out_odom.pose.pose)
        self._cloud_pub.publish(
            point_cloud2.create_cloud_xyz32(header, published.tolist()))
        self._odom_pub.publish(out_odom)
        self._pose_pub.publish(out_pose)
        transform = world_base_transform(
            self._child_frame, header.stamp,
            (out_odom.pose.pose.position.x, out_odom.pose.pose.position.y,
             out_odom.pose.pose.position.z), orientation)
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
    uav_count = contract.get("uav_count")
    if not isinstance(uav_count, int) or isinstance(uav_count, bool) or uav_count < 2:
        raise ValueError("GT mapper requires at least two vehicles")
    if len(contract.get("vehicles", [])) != uav_count:
        raise ValueError("GT mapper vehicle list must match uav_count")
    return contract


def self_test():
    from types import SimpleNamespace

    assert IRIS_COLLISION_GEOMETRY_ID == (
        "iris.sdf.jinja:e8ae6d24c7d85124326db2f795aa72286772da3520110419919a897527d73225")
    assert IRIS_COLLISION_PRIMITIVES == (
        ("box", (0.0, 0.0, 0.0), (0.47, 0.47, 0.11)),
        ("cylinder", (0.13, -0.22, 0.023), (0.128, 0.005)),
        ("cylinder", (-0.13, 0.2, 0.023), (0.128, 0.005)),
        ("cylinder", (0.13, 0.22, 0.023), (0.128, 0.005)),
        ("cylinder", (-0.13, -0.2, 0.023), (0.128, 0.005)),
        ("box", (0.0, 0.0, 0.05), (0.15, 0.1, 0.1)),
    )
    raw = [[0.1, 0.0, 0.0], [1.0, 0.0, 0.0],
           [21.0, 0.0, 0.0], [math.nan, 0.0, 0.0]]
    filtered, counts = filter_and_decimate_points(raw, stride=1)
    assert filtered.shape == (1, 3)
    assert counts == {"nonfinite": 1, "near": 1, "far": 1}
    registered = register_points(
        filtered, (0.0, 0.0, 0.0, 1.0), (0.0, 0.0, 1.0),
        (1.5, 0.0, 0.0))
    assert np.allclose(registered[0], [2.5, 0.0, 1.13])
    assert LIDAR_SENSOR_OFFSET_M == (0.0, 0.0, 0.13)
    roll_pitch_yaw = (0.1262851727171679, -0.12611650708648509,
                      0.2100786483669295, 0.96125628387669)
    source_body = (-1.0, 0.5, 0.25)
    source_sensor = lidar_sensor_world_origin(
        roll_pitch_yaw, source_body, (1.5, 0.0, 0.0))
    assert np.allclose(source_sensor, register_points(
        np.zeros((1, 3), dtype=np.float32), roll_pitch_yaw, source_body,
        (1.5, 0.0, 0.0))[0])
    rotated_endpoint = register_points(
        np.asarray([[0.7, -0.5, 0.2]], dtype=np.float32), roll_pitch_yaw,
        source_body, (1.5, 0.0, 0.0))[0]
    rotated_peer = pose_record(
        10.0, tuple((source_sensor + rotated_endpoint) / 2.0),
        (0.0, 0.0, 0.0, 1.0))
    rotated_source = pose_record(10.0, source_sensor, roll_pitch_yaw)
    assert peer_ray_intersection_mask(
        np.asarray([rotated_endpoint], dtype=np.float32), rotated_source,
        rotated_peer).tolist() == [True]
    # Regression: a body-origin ray would hit this peer box, while the matching
    # LiDAR-origin ray correctly bypasses it because the sensor is above body.
    yaw = (0.0, 0.0, math.sqrt(0.5), math.sqrt(0.5))
    legacy_body = (-1.0, 0.17, 0.0)
    legacy_endpoint = register_points(
        np.asarray([[0.0, -3.0, -0.3]], dtype=np.float32), yaw,
        legacy_body, (0.0, 0.0, 0.0))
    legacy_peer = pose_record(10.0, (0.0, 0.23, -0.05),
                              (0.0, 0.0, 0.0, 1.0))
    sensor_source = pose_record(
        10.0, lidar_sensor_world_origin(yaw, legacy_body, (0.0, 0.0, 0.0)), yaw)
    body_source = pose_record(10.0, legacy_body, yaw)
    assert not peer_ray_intersection_mask(legacy_endpoint, sensor_source, legacy_peer)[0]
    assert peer_ray_intersection_mask(legacy_endpoint, body_source, legacy_peer)[0]
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
    local_pose = SimpleNamespace(
        pose=SimpleNamespace(
            position=SimpleNamespace(x=0.0, y=2.0, z=3.0),
            orientation=SimpleNamespace(x=0.0, y=0.0, z=0.0, w=1.0)))
    initial_uav1 = (1.5, 0.0, 0.0)
    registered_pose = offset_pose_copy(local_pose, initial_uav1)
    assert (registered_pose.pose.position.x, registered_pose.pose.position.y,
            registered_pose.pose.position.z) == (1.5, 2.0, 3.0)
    assert (local_pose.pose.position.x, local_pose.pose.position.y,
            local_pose.pose.position.z) == (0.0, 2.0, 3.0)
    callback_order_ledger = PoseLedger()
    # Model the synchronizer callback first, then the raw-odom ledger callback.
    offset_pose_copy(local_pose, initial_uav1)
    assert callback_order_ledger.update(
        "uav1", 10.0,
        (local_pose.pose.position.x + initial_uav1[0],
         local_pose.pose.position.y + initial_uav1[1],
         local_pose.pose.position.z + initial_uav1[2]),
        (local_pose.pose.orientation.x, local_pose.pose.orientation.y,
         local_pose.pose.orientation.z, local_pose.pose.orientation.w))
    offset_pose_copy(local_pose, initial_uav1)
    assert callback_order_ledger.update(
        "uav1", 10.1,
        (local_pose.pose.position.x + initial_uav1[0],
         local_pose.pose.position.y + initial_uav1[1],
         local_pose.pose.position.z + initial_uav1[2]),
        (local_pose.pose.orientation.x, local_pose.pose.orientation.y,
         local_pose.pose.orientation.z, local_pose.pose.orientation.w))
    assert callback_order_ledger.snapshot()["uav1"]["position"] == (1.5, 2.0, 3.0)
    identity_pose = pose_record(10.0, (0.0, 0.0, 0.0), (0.0, 0.0, 0.0, 1.0))
    quarter_turn_pose = pose_record(10.0, (0.0, 0.0, 0.0),
                                    (0.0, 0.0, math.sqrt(0.5), math.sqrt(0.5)))
    points = np.asarray([[0.2, 0.0, 0.0], [0.0, 0.2, 0.0], [0.0, 0.5, 0.0]],
                        dtype=np.float32)
    assert points_in_iris_collision_envelope(points, identity_pose).tolist() == [True, True, False]
    assert points_in_iris_collision_envelope(points, quarter_turn_pose).tolist() == [True, True, False]
    rotation_only = np.asarray([[-0.34, 0.09, 0.023]], dtype=np.float32)
    assert not points_in_iris_collision_envelope(rotation_only, identity_pose)[0]
    assert points_in_iris_collision_envelope(rotation_only, quarter_turn_pose)[0]
    poses = {"uav0": identity_pose,
             "uav1": pose_record(10.0, (1.5, 0.0, 0.0), (0.0, 0.0, 0.0, 1.0))}
    candidates = classify_body_candidates(
        np.asarray([[0.0, 0.0, 0.0], [1.5, 0.0, 0.0], [4.0, 0.0, 0.0]], dtype=np.float32),
        "uav0", "uav1", 10.0, poses)
    assert candidates["self_candidates"] == 1 and candidates["peer_candidates"] == 1
    assert candidates["self_pose_status"] == candidates["peer_pose_status"] == "available"
    peer_input = np.asarray(
        [[0.0, 0.0, 0.0], [1.5, 0.0, 0.0], [4.0, 0.0, 0.0]], dtype=np.float32)
    peer_filtered, peer_result = peer_body_filter(
        peer_input, "uav0", "uav1", 10.0, poses)
    assert np.array_equal(peer_filtered, np.asarray(
        [[0.0, 0.0, 0.0]], dtype=np.float32))
    assert peer_result["registered_points"] == 3
    assert peer_result["published_points"] == 1
    assert peer_result["self_candidates"] == 1
    assert peer_result["peer_candidates"] == peer_result["peer_endpoint_candidates"] == 1
    assert peer_result["peer_inflation_endpoint_candidates"] == 1
    assert peer_result["peer_ray_candidates"] == 2
    assert peer_result["peer_removed_points"] == 2
    assert peer_result["published_points"] == (
        peer_result["registered_points"] - peer_result["peer_removed_points"])
    assert peer_result["peer_preserved_unavailable_points"] == 0
    # D7: multi-peer filter equals single-peer for one peer and unions N peers.
    single_peer_multi, single_peer_multi_result = multi_peer_body_filter(
        peer_input, "uav0", ("uav1",), 10.0, poses)
    assert np.array_equal(single_peer_multi, peer_filtered)
    assert single_peer_multi_result == peer_result
    two_peer_poses = {
        "uav0": identity_pose,
        "uav1": pose_record(10.0, (1.5, 0.0, 0.0), (0.0, 0.0, 0.0, 1.0)),
        "uav2": pose_record(10.0, (-1.5, 0.0, 0.0), (0.0, 0.0, 0.0, 1.0)),
    }
    two_peer_input = np.asarray(
        [[0.0, 0.0, 0.0], [1.5, 0.0, 0.0], [-1.5, 0.0, 0.0], [4.0, 0.0, 0.0]],
        dtype=np.float32)
    two_peer_published, two_peer_result = multi_peer_body_filter(
        two_peer_input, "uav0", ("uav1", "uav2"), 10.0, two_peer_poses)
    assert np.array_equal(two_peer_published, np.asarray([[0.0, 0.0, 0.0]], dtype=np.float32))
    assert two_peer_result["registered_points"] == 4
    assert two_peer_result["published_points"] == 1
    assert two_peer_result["peer_endpoint_candidates"] == 2
    assert two_peer_result["peer_removed_points"] == 3
    missing_peer_published, missing_peer_result = multi_peer_body_filter(
        two_peer_input, "uav0", ("uav1", "uav9"), 10.0, two_peer_poses)
    assert missing_peer_result["peer_preserved_unavailable_points"] == 0
    assert missing_peer_result["peer_removed_points"] == 2
    assert np.array_equal(missing_peer_published, np.asarray(
        [[0.0, 0.0, 0.0], [-1.5, 0.0, 0.0]], dtype=np.float32))
    ray_peer = pose_record(10.0, (0.0, 0.0, 0.0), (0.0, 0.0, 0.0, 1.0))
    ray_source = pose_record(10.0, (-1.0, 0.0, 0.0), (0.0, 0.0, 0.0, 1.0))
    ray_points = np.asarray(
        [[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [1.0, 1.0, 0.0]], dtype=np.float32)
    ray_original = ray_points.copy()
    endpoint_mask = points_in_iris_collision_envelope(ray_points, ray_peer)
    ray_mask = peer_ray_intersection_mask(ray_points, ray_source, ray_peer)
    assert endpoint_mask.tolist() == [True, False, False]
    assert ray_mask.tolist() == [True, True, False]
    ray_published, ray_result = peer_body_filter(
        ray_points, "uav0", "uav1", 10.0,
        {"uav0": ray_source, "uav1": ray_peer}, source_scan_pose=ray_source)
    assert np.array_equal(ray_published, np.asarray([[1.0, 1.0, 0.0]], dtype=np.float32))
    assert ray_result["peer_endpoint_candidates"] == 1
    assert ray_result["peer_inflation_endpoint_candidates"] == 1
    assert ray_result["peer_ray_candidates"] == 2
    assert ray_result["peer_removed_points"] == 2
    assert ray_result["published_points"] == 1
    assert np.array_equal(ray_points, ray_original)
    assert not points_in_iris_collision_envelope(
        np.asarray([ray_source["position"]], dtype=np.float32), ray_peer)[0]
    tangent_source = pose_record(10.0, (-1.0, 0.235, 0.0), (0.0, 0.0, 0.0, 1.0))
    tangent_endpoint = np.asarray([[1.0, 0.235, 0.0]], dtype=np.float32)
    assert peer_ray_intersection_mask(tangent_endpoint, tangent_source, ray_peer).tolist() == [True]
    rotated_ray_peer = quarter_turn_pose
    rotated_ray_source = pose_record(
        10.0, (-0.2, -1.0, 0.023), (0.0, 0.0, 0.0, 1.0))
    rotated_ray_endpoint = np.asarray([[-0.2, 1.0, 0.023]], dtype=np.float32)
    assert peer_ray_intersection_mask(
        rotated_ray_endpoint, rotated_ray_source, rotated_ray_peer).tolist() == [True]
    inflation_peer = pose_record(10.0, UAV1_HOVER_WORLD, (0.0, 0.0, 0.0, 1.0))
    inflation_source = pose_record(10.0, (1.5, 2.0, 1.5), (0.0, 0.0, 0.0, 1.0))
    inflation_points = np.asarray([
        [1.5, 0.0, 1.5], [1.9, 0.0, 1.5],
        [2.084, 0.0, 1.5], [2.086, 0.0, 1.5], [10.0, 10.0, 1.5]],
        dtype=np.float32)
    inflation_original = inflation_points.copy()
    assert points_in_iris_collision_envelope(
        inflation_points, inflation_peer).tolist() == [True, False, False, False, False]
    assert points_in_iris_inflation_neighborhood(
        inflation_points, inflation_peer).tolist() == [True, True, True, False, False]
    inflation_published, inflation_result = peer_body_filter(
        inflation_points, "uav0", "uav1", 10.0,
        {"uav0": inflation_source, "uav1": inflation_peer},
        source_scan_pose=inflation_source)
    assert np.array_equal(inflation_published, np.asarray(
        [[2.086, 0.0, 1.5], [10.0, 10.0, 1.5]], dtype=np.float32))
    assert inflation_result["peer_endpoint_candidates"] == 1
    assert inflation_result["peer_inflation_endpoint_candidates"] == 3
    assert inflation_result["peer_removed_points"] == 3
    assert inflation_result["published_points"] == (
        inflation_result["registered_points"] - inflation_result["peer_removed_points"])
    assert np.array_equal(inflation_points, inflation_original)
    tangent_inflation = np.asarray([[0.585, 0.0, 0.0]], dtype=np.float32)
    assert points_in_iris_inflation_neighborhood(tangent_inflation, ray_peer)[0]
    assert not points_in_iris_inflation_neighborhood(
        np.asarray([[0.585001, 0.0, 0.0]], dtype=np.float32), ray_peer)[0]
    rotated_inflation_point = np.asarray([[-0.65, -0.25, 0.023]], dtype=np.float32)
    assert not points_in_iris_collision_envelope(rotated_inflation_point, quarter_turn_pose)[0]
    assert points_in_iris_inflation_neighborhood(rotated_inflation_point, quarter_turn_pose)[0]
    assert not points_in_iris_inflation_neighborhood(rotated_inflation_point, identity_pose)[0]
    missing_filtered, missing_result = peer_body_filter(
        peer_input, "uav0", "uav1", 10.0, {"uav0": identity_pose})
    assert np.array_equal(missing_filtered, peer_input)
    assert missing_result["peer_pose_status"] == "missing"
    assert missing_result["peer_removed_points"] == 0
    assert missing_result["peer_preserved_unavailable_points"] == len(peer_input)
    stale_filtered, stale_result = peer_body_filter(
        peer_input, "uav0", "uav1", 10.2, poses)
    assert np.array_equal(stale_filtered, peer_input)
    assert stale_result["peer_pose_status"] == "stale"
    assert stale_result["peer_removed_points"] == 0
    provenance_counts = {
        "uav1_hover_voxels": {},
        "peer_unavailable_body_candidates": 0,
        "peer_unavailable_inflation_candidates": 0,
        "peer_unavailable_pose_status": {},
    }
    provenance_input = np.asarray([[1.5, 0.0, 1.5], [1.9, 0.0, 1.5]],
                                  dtype=np.float32)
    provenance_original = provenance_input.copy()
    stale_hover_peer = pose_record(
        10.0, UAV1_HOVER_WORLD, (0.0, 0.0, 0.0, 1.0))
    # A stale pose is recorded as hypothetical provenance only; the existing
    # fail-safe publication path still retains every point.
    record_provenance_diagnostic(
        provenance_counts, provenance_input, "uav0", 10.2, stale_hover_peer, "stale")
    record_provenance_diagnostic(
        provenance_counts, provenance_input, "uav0", 10.3, stale_hover_peer, "stale")
    assert np.array_equal(provenance_input, provenance_original)
    assert provenance_counts["peer_unavailable_body_candidates"] == 2
    assert provenance_counts["peer_unavailable_inflation_candidates"] == 4
    assert provenance_counts["peer_unavailable_pose_status"] == {"stale": 2}
    hover = provenance_counts["uav1_hover_voxels"]
    assert len(hover) == 1
    hover_record = next(iter(hover.values()))
    assert hover_record == {"source_uav": "uav0", "point_hits": 2,
                            "first_sim_time": 10.2, "recent_sim_time": 10.3}
    published_before, result_before = peer_body_filter(
        provenance_input, "uav0", "uav1", 10.2, poses)
    record_provenance_diagnostic(
        provenance_counts, provenance_input, "uav0", 10.2, stale_hover_peer, "stale")
    published_after, result_after = peer_body_filter(
        provenance_input, "uav0", "uav1", 10.2, poses)
    assert np.array_equal(published_before, published_after)
    assert result_before == result_after
    available_counts = {
        "uav1_hover_voxels": {}, "peer_unavailable_body_candidates": 0,
        "peer_unavailable_inflation_candidates": 0,
        "peer_unavailable_pose_status": {}}
    available_poses = {"uav0": identity_pose, "uav1": stale_hover_peer}
    available_published, available_result = peer_body_filter(
        provenance_input, "uav0", "uav1", 10.0, available_poses)
    assert available_published.shape == (0, 3)
    assert available_result["peer_inflation_endpoint_candidates"] == 2
    record_provenance_diagnostic(
        available_counts, available_published, "uav0", 10.0,
        stale_hover_peer, available_result["peer_pose_status"])
    assert available_counts == {
        "uav1_hover_voxels": {}, "peer_unavailable_body_candidates": 0,
        "peer_unavailable_inflation_candidates": 0,
        "peer_unavailable_pose_status": {}}
    missing_provenance = {
        "uav1_hover_voxels": {}, "peer_unavailable_body_candidates": 0,
        "peer_unavailable_inflation_candidates": 0,
        "peer_unavailable_pose_status": {}}
    record_provenance_diagnostic(
        missing_provenance, provenance_input, "uav0", 10.2, None, "missing")
    assert missing_provenance["peer_unavailable_body_candidates"] == 0
    assert missing_provenance["peer_unavailable_inflation_candidates"] == 0
    assert missing_provenance["peer_unavailable_pose_status"] == {"missing": 1}
    record_provenance_diagnostic(
        missing_provenance, provenance_input, "uav0", 10.2,
        stale_hover_peer, "uncomparable")
    assert missing_provenance["peer_unavailable_pose_status"] == {
        "missing": 1, "uncomparable": 1}
    nonfinite_filtered, nonfinite_result = peer_body_filter(
        peer_input, "uav0", "uav1", 10.0,
        {"uav0": identity_pose,
         "uav1": pose_record(10.0, (math.nan, 0.0, 0.0), (0.0, 0.0, 0.0, 1.0))})
    assert np.array_equal(nonfinite_filtered, peer_input)
    assert nonfinite_result["peer_pose_status"] == "missing"
    rotated_filtered, rotated_result = peer_body_filter(
        np.asarray([[-0.34, 0.09, 0.023], [4.0, 0.0, 0.0]], dtype=np.float32),
        "uav0", "uav1", 10.0,
        {"uav0": pose_record(10.0, (4.0, 0.0, 0.0), (0.0, 0.0, 0.0, 1.0)),
         "uav1": quarter_turn_pose})
    assert rotated_result["peer_removed_points"] == 1
    assert np.array_equal(rotated_filtered, np.asarray([[4.0, 0.0, 0.0]], dtype=np.float32))
    empty_filtered, empty_result = peer_body_filter(
        np.asarray([[1.5, 0.0, 0.0]], dtype=np.float32), "uav0", "uav1", 10.0, poses)
    assert empty_filtered.shape == (0, 3)
    assert empty_result["published_points"] == 0
    assert pose_record(10.0, (math.nan, 0.0, 0.0), (0.0, 0.0, 0.0, 1.0)) is None
    original = points.copy()
    classify_body_candidates(points, "uav0", "uav1", 10.0, poses)
    assert np.array_equal(points, original)
    reverse = classify_body_candidates(
        np.asarray([[0.0, 0.0, 0.0], [1.5, 0.0, 0.0]], dtype=np.float32),
        "uav1", "uav0", 10.0, poses)
    assert reverse["self_candidates"] == 1 and reverse["peer_candidates"] == 1
    ledger = PoseLedger()
    assert ledger.update("uav0", 10.00, (0.0, 0.0, 0.0), (0.0, 0.0, 0.0, 1.0))
    assert ledger.update("uav1", 10.03, (1.5, 0.0, 0.0), (0.0, 0.0, 0.0, 1.0))
    assert not ledger.update("uav0", 9.99, (9.0, 0.0, 0.0), (0.0, 0.0, 0.0, 1.0))
    ledger_poses = ledger.snapshot()
    assert ledger_poses["uav0"]["position"] == (0.0, 0.0, 0.0)
    assert pose_freshness(ledger_poses["uav1"], 10.02) == "available"
    assert pose_freshness(ledger_poses["uav0"], 10.03) == "available"
    forward_filtered, forward_result = peer_body_filter(
        np.asarray([[1.5, 0.0, 0.0]], dtype=np.float32),
        "uav0", "uav1", 10.02, ledger_poses)
    reverse_filtered, reverse_result = peer_body_filter(
        np.asarray([[0.0, 0.0, 0.0]], dtype=np.float32),
        "uav1", "uav0", 10.03, ledger_poses)
    assert forward_filtered.shape == reverse_filtered.shape == (0, 3)
    assert forward_result["peer_candidates"] == reverse_result["peer_candidates"] == 1
    source_counts = {"raw_points": 3, "self_pose_status": {"available": 1},
                     "peer_pose_status": {"missing": 1}}
    snapshot = body_diagnostic_snapshot(source_counts, "uav0", "uav1")
    source_counts["raw_points"] = 99
    source_counts["self_pose_status"]["available"] = 2
    assert snapshot["raw_points"] == 3
    assert snapshot["self_pose_status"] == {"available": 1}
    other_counts = {"raw_points": 4, "self_pose_status": {"stale": 1},
                    "peer_pose_status": {"available": 1}}
    other_snapshot = body_diagnostic_snapshot(other_counts, "uav1", "uav0")
    other_counts["peer_pose_status"]["available"] = 2
    assert other_snapshot["peer_pose_status"] == {"available": 1}
    assert snapshot["self_pose_status"] is not other_snapshot["self_pose_status"]
    # D7: load_contract accepts any uav_count >= 2 and pins it to vehicles.
    three_contract = load_contract(
        str(Path(__file__).resolve().parents[1] / "config/3uav_static.yaml"))
    assert three_contract["uav_count"] == 3
    assert [spec["name"] for spec in three_contract["vehicles"]] == [
        "uav0", "uav1", "uav2"]
    two_contract = load_contract(
        str(Path(__file__).resolve().parents[1] / "config/2uav_static.yaml"))
    assert two_contract["uav_count"] == 2
    import tempfile
    with tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False) as stream:
        stream.write("registration_source: gt\nuav_count: 1\nvehicles: []\n")
        one_contract_path = stream.name
    try:
        load_contract(one_contract_path)
        raise AssertionError("expected ValueError for uav_count=1")
    except ValueError:
        pass
    finally:
        Path(one_contract_path).unlink()
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
    ledger = PoseLedger()
    names = [spec["name"] for spec in contract["vehicles"]]
    mappers = [VehicleMapper(spec, ledger,
                             tuple(name for name in names if name != spec["name"]))
               for spec in contract["vehicles"]]
    rospy.loginfo("two_uav_gt_mapper ready for %s",
                  ", ".join(mapper._spec["name"] for mapper in mappers))
    rospy.spin()


if __name__ == "__main__":
    main()
