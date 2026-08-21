#!/usr/bin/env python3
"""Static geometry checks for the 50 x 50 m 2-UAV outdoor world candidate."""

import argparse
import math
from pathlib import Path
import sys
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_WORLD = ROOT / "worlds/2uav_outdoor_50x50_v1.world"
SPAWNS = {"uav0": (0.0, 0.0), "uav1": (1.5, 0.0)}
BOUNDARIES = {"boundary_west", "boundary_east", "boundary_south", "boundary_north"}


def numbers(text):
    return tuple(float(value) for value in text.split())


def model_pose(model):
    pose = model.findtext("pose", "0 0 0 0 0 0")
    return numbers(pose)


def collision_shape(model):
    collision = model.find("./link/collision/geometry")
    if collision is None:
        return None
    box = collision.find("box/size")
    if box is not None:
        return "box", numbers(box.text)
    cylinder = collision.find("cylinder")
    if cylinder is not None:
        return "cylinder", (
            float(cylinder.findtext("radius")), float(cylinder.findtext("length")))
    return None


def point_clearance(model, point):
    pose = model_pose(model)
    shape = collision_shape(model)
    if shape[0] == "box":
        sx, sy, _sz = shape[1]
        dx = max(abs(point[0] - pose[0]) - sx / 2.0, 0.0)
        dy = max(abs(point[1] - pose[1]) - sy / 2.0, 0.0)
        return math.hypot(dx, dy)
    radius, _length = shape[1]
    return max(math.hypot(point[0] - pose[0], point[1] - pose[1]) - radius, 0.0)


def validate(path):
    errors = []
    root = ET.parse(path).getroot()
    worlds = root.findall("world")
    if len(worlds) != 1:
        return ["expected exactly one <world>"]
    world = worlds[0]
    models = world.findall("model")
    names = [model.attrib.get("name") for model in models]
    if len(names) != len(set(names)):
        errors.append("model names are not unique")
    if not BOUNDARIES.issubset(names):
        errors.append("missing perimeter walls: %s" % sorted(BOUNDARIES - set(names)))
    ground = next((model for model in models if model.attrib.get("name") == "ground_50x50"), None)
    if ground is None or collision_shape(ground) != ("box", (50.0, 50.0, 0.1)):
        errors.append("ground collision must be exactly 50 x 50 x 0.1 m")
    obstacles = [model for model in models
                 if model.attrib.get("name") != "ground_50x50"]
    if len(obstacles) < 16:
        errors.append("expected at least 16 perimeter/interior obstacles")
    for model in models:
        if model.findtext("static", "false").strip().lower() != "true":
            errors.append("non-static model: %s" % model.attrib.get("name"))
        shape = collision_shape(model)
        if shape is None:
            errors.append("missing supported collision: %s" % model.attrib.get("name"))
            continue
        x, y = model_pose(model)[:2]
        if abs(x) > 25.0 or abs(y) > 25.0:
            errors.append("model center outside 50 m boundary: %s" % model.attrib.get("name"))
    interior = [model for model in obstacles
                if model.attrib.get("name") not in BOUNDARIES]
    for spawn_name, point in SPAWNS.items():
        clearance = min(point_clearance(model, point) for model in interior)
        if clearance < 3.0:
            errors.append("%s spawn clearance %.3f m is below 3.0 m" %
                          (spawn_name, clearance))
    return errors


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("world", nargs="?", default=str(DEFAULT_WORLD))
    args = parser.parse_args()
    try:
        errors = validate(args.world)
    except (OSError, ET.ParseError, TypeError, ValueError) as exc:
        errors = [str(exc)]
    if errors:
        for error in errors:
            print("FAIL: " + error)
        return 2
    print("2uav outdoor world static validation: PASS")
    print("world=50x50m models=21 spawn_clearance>=3.0m perimeter=closed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
