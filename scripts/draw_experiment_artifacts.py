#!/usr/bin/env python3
"""Render per-run grid path and point cloud figures for a 3-UAV smoke run.

grid_path.png    : top-down occupancy grid of the UAV-built map, overlaid with
                   per-UAV trajectories from telemetry.jsonl.
point_cloud.png  : 3-D point cloud of the UAV-built map voxels plus UAV traces.

Map data source priority:
  1. per-UAV coverage_voxels.json (written by two_uav_collector.finalize).
     Voxel indices are world-space 0.25 m grid indices as produced by the
     collector (floor(x / 0.25), floor(y / 0.25), floor(z / 0.25)).
  2. world truth obstacle voxels rasterized from the SDF world file at
     --resolution, used only when no observed voxel dump exists.
"""
import argparse
import json
import math
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap
from mpl_toolkits.mplot3d import Axes3D  # noqa: F401
import numpy as np
import xml.etree.ElementTree as ET

DEFAULT_WORLD = Path(
    "/home/houslakers/auto_tune_racer/racer-platform/environment/worlds/"
    "2uav_outdoor_50x50_v1.world")
VEHICLE_COLORS = {"uav0": "#1f77b4", "uav1": "#2ca02c", "uav2": "#d62728",
                  "uav3": "#9467bd", "uav4": "#ff7f0e", "uav5": "#8c564b"}
COLLECTOR_VOXEL_M = 0.25  # world-space index size used by two_uav_collector


def world_obstacle_voxels(world_path, box_min, box_max, resolution):
    """Rasterize world collision geometry into world-space voxel centers.

    Returns ({(x, y, z)}, (nx, ny, nz)) where every returned point is the
    center of a 0.25 m cube in world coordinates.
    """
    root = ET.parse(world_path).getroot()
    nx = max(1, int(math.ceil((box_max[0] - box_min[0]) / resolution)))
    ny = max(1, int(math.ceil((box_max[1] - box_min[1]) / resolution)))
    nz = max(1, int(math.ceil((box_max[2] - box_min[2]) / resolution)))
    indices = set()
    for model in root.findall(".//model"):
        name = model.attrib.get("name", "")
        if name.startswith("ground"):
            continue
        pose = [float(v) for v in (model.findtext("pose") or "0 0 0 0 0 0").split()]
        cx, cy, cz = pose[:3]
        for box in model.findall(".//collision//box"):
            sx, sy, sz = [float(v) for v in box.findtext("size").split()]
            x0, x1 = cx - sx / 2, cx + sx / 2
            y0, y1 = cy - sy / 2, cy + sy / 2
            z0, z1 = cz - sz / 2, cz + sz / 2
            for ix in range(nx):
                x = box_min[0] + (ix + 0.5) * resolution
                if not (x0 <= x <= x1):
                    continue
                for iy in range(ny):
                    y = box_min[1] + (iy + 0.5) * resolution
                    if not (y0 <= y <= y1):
                        continue
                    for iz in range(nz):
                        z = box_min[2] + (iz + 0.5) * resolution
                        if z0 <= z <= z1:
                            indices.add((ix, iy, iz))
        for cyl in model.findall(".//collision//cylinder"):
            r = float(cyl.findtext("radius"))
            h = float(cyl.findtext("length")) if cyl.findtext("length") else 2.0
            z0, z1 = cz - h / 2, cz + h / 2
            for ix in range(nx):
                x = box_min[0] + (ix + 0.5) * resolution
                if abs(x - cx) > r:
                    continue
                for iy in range(ny):
                    y = box_min[1] + (iy + 0.5) * resolution
                    if (x - cx) ** 2 + (y - cy) ** 2 > r * r:
                        continue
                    for iz in range(nz):
                        z = box_min[2] + (iz + 0.5) * resolution
                        if z0 <= z <= z1:
                            indices.add((ix, iy, iz))
    # Convert raster indices to world-space 0.25 m voxel centers so both map
    # sources use the same coordinate convention.
    points = {(box_min[0] + (i + 0.5) * resolution,
               box_min[1] + (j + 0.5) * resolution,
               box_min[2] + (k + 0.5) * resolution)
              for i, j, k in indices}
    return points


def load_telemetry(runroot):
    positions = {}
    for vehicle_dir in sorted(runroot.iterdir()):
        if not vehicle_dir.is_dir():
            continue
        tel = vehicle_dir / "telemetry.jsonl"
        if not tel.is_file():
            continue
        pts = []
        for raw in tel.read_text(encoding="utf-8").splitlines():
            if not raw:
                continue
            try:
                item = json.loads(raw)
            except Exception:
                continue
            pos = item.get("position")
            if isinstance(pos, list) and len(pos) == 3:
                pts.append(tuple(pos))
        positions[vehicle_dir.name] = pts
    return positions


def load_observed_voxels(runroot):
    """Per-vehicle observed occupancy voxels dumped by the collector.

    Returns {vehicle: {(x, y, z), ...}} with world-space centers at
    (ix + 0.5) * 0.25.
    """
    dumps = {}
    for vehicle_dir in sorted(runroot.iterdir()):
        if not vehicle_dir.is_dir():
            continue
        path = vehicle_dir / "coverage_voxels.json"
        if not path.is_file():
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        dumps[vehicle_dir.name] = {
            ((int(v[0]) + 0.5) * COLLECTOR_VOXEL_M,
             (int(v[1]) + 0.5) * COLLECTOR_VOXEL_M,
             (int(v[2]) + 0.5) * COLLECTOR_VOXEL_M)
            for v in data["voxels"]}
    return dumps


def _grid_from_points(points, box_min, box_max, resolution):
    """Rasterize a set of world-space (x, y, z) points into a 2-D grid."""
    nx = max(1, int(math.ceil((box_max[0] - box_min[0]) / resolution)))
    ny = max(1, int(math.ceil((box_max[1] - box_min[1]) / resolution)))
    grid = np.zeros((ny, nx), dtype=np.uint8)
    for x, y, _z in points:
        ix = int(math.floor((x - box_min[0]) / resolution))
        iy = int(math.floor((y - box_min[1]) / resolution))
        if 0 <= ix < nx and 0 <= iy < ny:
            grid[iy, ix] = 1
    return grid


def plot_grid_path(runroot, box_min, box_max, resolution, map_points,
                   observed, trajectories, out_path):
    grid = _grid_from_points(map_points, box_min, box_max, resolution)
    fig, ax = plt.subplots(figsize=(10, 10))
    cmap = ListedColormap(["#ffffff", "#2f4f4f"])
    ax.imshow(grid, origin="lower", extent=[box_min[0], box_max[0],
                                            box_min[1], box_max[1]],
              cmap=cmap, alpha=0.9, interpolation="nearest", zorder=1)
    for name, pts in trajectories.items():
        if not pts:
            continue
        color = VEHICLE_COLORS.get(name, "#333333")
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        ax.plot(xs, ys, lw=2.0, color=color, label=f"{name} path", zorder=3)
        ax.scatter(xs[0], ys[0], s=120, marker="*", color=color,
                   edgecolor="k", zorder=4, label=f"{name} start")
        ax.scatter(xs[-1], ys[-1], s=45, marker="o", color=color,
                   edgecolor="k", zorder=4)
    ax.set_xlim(box_min[0] - 0.5, box_max[0] + 0.5)
    ax.set_ylim(box_min[1] - 0.5, box_max[1] + 0.5)
    ax.set_aspect("equal")
    ax.set_title(f"{runroot.name} — grid path\n"
                 f"dark cells: {'UAV-built occupancy map' if observed else 'world obstacle voxels (truth)'} "
                 f"@{resolution} m", fontsize=11)
    ax.set_xlabel("x (m)")
    ax.set_ylabel("y (m)")
    ax.grid(True, ls=":", alpha=0.35, zorder=2)
    ax.legend(loc="upper left", fontsize=8, ncol=2)
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)


def plot_point_cloud(runroot, box_min, box_max, _resolution, map_points,
                     observed, trajectories, out_path):
    fig = plt.figure(figsize=(10, 8))
    ax = fig.add_subplot(111, projection="3d")
    for name, pts in trajectories.items():
        if not pts:
            continue
        color = VEHICLE_COLORS.get(name, "#333333")
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        zs = [p[2] for p in pts]
        ax.plot(xs, ys, zs, lw=1.4, color=color, label=f"{name} trace")
    if map_points:
        xs = [p[0] for p in map_points]
        ys = [p[1] for p in map_points]
        zs = [p[2] for p in map_points]
        ax.scatter(xs, ys, zs, s=0.6, alpha=0.35, c="#4a4a4a",
                   label="UAV-built map voxels" if observed
                   else "world obstacle voxels (truth)")
    ax.set_title(f"{runroot.name} — point cloud\n"
                 f"{'UAV-built map voxels' if observed else 'world obstacle voxels (truth)'} "
                 f"+ UAV traces", fontsize=11)
    ax.set_xlabel("x (m)")
    ax.set_ylabel("y (m)")
    ax.set_zlabel("z (m)")
    ax.set_xlim(box_min[0], box_max[0])
    ax.set_ylim(box_min[1], box_max[1])
    ax.set_zlim(box_min[2], box_max[2])
    ax.view_init(elev=25, azim=-55)
    ax.legend(loc="upper right", fontsize=8)
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--runroot", required=True, type=Path)
    parser.add_argument("--world", type=Path, default=DEFAULT_WORLD)
    parser.add_argument("--resolution", type=float, default=0.25)
    args = parser.parse_args()

    box_min = (-24.5, -24.5, 0.0)
    box_max = (24.5, 24.5, 3.0)

    trajectories = load_telemetry(args.runroot)
    observed = load_observed_voxels(args.runroot)
    if observed:
        map_points = set().union(*observed.values())
    else:
        map_points = world_obstacle_voxels(
            args.world, box_min, box_max, args.resolution)

    plot_grid_path(args.runroot, box_min, box_max, args.resolution, map_points,
                   bool(observed), trajectories,
                   args.runroot / "grid_path.png")
    plot_point_cloud(args.runroot, box_min, box_max, args.resolution, map_points,
                     bool(observed), trajectories,
                     args.runroot / "point_cloud.png")
    print("wrote", args.runroot / "grid_path.png")
    print("wrote", args.runroot / "point_cloud.png")


if __name__ == "__main__":
    main()
