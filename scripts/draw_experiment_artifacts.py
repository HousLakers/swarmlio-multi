#!/usr/bin/env python3
"""Render multi-UAV experiment artifacts in the single-UAV visual style.

Outputs:
- coverage.png: top panel is top-down point cloud + trajectories;
                bottom panel is cumulative unique coverage voxels vs sim time.
- grid_map.png: 5 cm raster occupancy map from observed coverage voxels.
- point_cloud.png: top-down occupancy point cloud + trajectories.

Map source priority:
1) per-vehicle coverage_voxels.json and coverage_seq.json written by the collector;
2) world obstacle voxels only when no observed coverage exists.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import xml.etree.ElementTree as ET

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

DEFAULT_WORLD = Path(
    "/home/houslakers/auto_tune_racer/racer-platform/environment/worlds/"
    "2uav_outdoor_50x50_v1.world")
VEHICLE_COLORS = {
    "uav0": "#1f77b4",
    "uav1": "#2ca02c",
    "uav2": "#d62728",
    "uav3": "#9467bd",
    "uav4": "#ff7f0e",
}
VOXEL_M = 0.25
GRID_RES = 0.05


def load_telemetry(runroot: Path):
    history = {}
    for vehicle_dir in sorted(runroot.iterdir()):
        if not vehicle_dir.is_dir():
            continue
        path = vehicle_dir / "telemetry.jsonl"
        if not path.is_file():
            continue
        pts = []
        for raw in path.read_text(encoding="utf-8").splitlines():
            if not raw:
                continue
            try:
                item = json.loads(raw)
            except Exception:
                continue
            pos = item.get("position")
            if isinstance(pos, list) and len(pos) == 3:
                pts.append(tuple(float(v) for v in pos))
        history[vehicle_dir.name] = pts
    return history


def load_coverage_voxels(runroot: Path):
    voxels = {}
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
        raw = data.get("voxels", [])
        pts = set()
        for item in raw:
            if isinstance(item, list) and len(item) == 3:
                pts.add(tuple((int(v) + 0.5) * VOXEL_M for v in item))
        voxels[vehicle_dir.name] = pts
    return voxels


def load_coverage_seq(runroot: Path):
    seq = {}
    for vehicle_dir in sorted(runroot.iterdir()):
        if not vehicle_dir.is_dir():
            continue
        path = vehicle_dir / "coverage_seq.json"
        if path.is_file():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                data = {}
            raw = data.get("coverage_seq", [])
            seq[vehicle_dir.name] = [
                (float(item[0]), int(item[1])) for item in raw
                if isinstance(item, list) and len(item) == 2
            ]
            continue
        # Fallback: derive the growth curve from telemetry.jsonl coverage snapshots.
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
            cov = item.get("coverage") or {}
            n = cov.get("observed_voxels")
            if not isinstance(n, int):
                continue
            t = cov.get("last_processed_wall_s") or cov.get("last_message_wall_s")
            if not isinstance(t, (int, float)):
                continue
            pts.append((float(t), int(n)))
        seq[vehicle_dir.name] = pts
    return seq


def world_obstacle_voxels(world_path: Path, box_min, box_max, res=GRID_RES):
    root = ET.parse(world_path).getroot()
    points = set()
    nx = max(1, int(math.ceil((box_max[0] - box_min[0]) / res)))
    ny = max(1, int(math.ceil((box_max[1] - box_min[1]) / res)))
    nz = max(1, int(math.ceil((box_max[2] - box_min[2]) / res)))
    for model in root.findall(".//model"):
        pose_text = model.findtext("pose") or "0 0 0 0 0 0"
        pose = [float(v) for v in pose_text.split()]
        cx, cy, cz = pose[:3]
        for box in model.findall(".//collision//box"):
            size_text = box.findtext("size")
            if not size_text:
                continue
            sx, sy, sz = [float(v) for v in size_text.split()]
            x0, x1 = cx - sx / 2.0, cx + sx / 2.0
            y0, y1 = cy - sy / 2.0, cy + sy / 2.0
            z0, z1 = cz - sz / 2.0, cz + sz / 2.0
            for ix in range(nx):
                x = box_min[0] + (ix + 0.5) * res
                if not (x0 <= x <= x1):
                    continue
                for iy in range(ny):
                    y = box_min[1] + (iy + 0.5) * res
                    if not (y0 <= y <= y1):
                        continue
                    for iz in range(nz):
                        z = box_min[2] + (iz + 0.5) * res
                        if z0 <= z <= z1:
                            points.add((x, y, z))
    return points


def rasterize(points, box_min, box_max, res=GRID_RES):
    width = max(1, int(math.ceil((box_max[0] - box_min[0]) / res)))
    height = max(1, int(math.ceil((box_max[1] - box_min[1]) / res)))
    grid = np.zeros((height, width), dtype=np.uint8)
    if not points:
        return grid
    xs = np.array([p[0] for p in points], dtype=np.float64)
    ys = np.array([p[1] for p in points], dtype=np.float64)
    ix = np.floor((xs - box_min[0]) / res).astype(np.int64)
    iy = np.floor((ys - box_min[1]) / res).astype(np.int64)
    valid = (ix >= 0) & (ix < width) & (iy >= 0) & (iy < height)
    grid[iy[valid], ix[valid]] = 255
    return grid


def union_points(points_by_vehicle):
    all_points = set()
    for pts in points_by_vehicle.values():
        all_points.update(pts)
    return all_points


def plot_coverage(runroot, box_min, box_max, trajectories, voxels_by_vehicle, seq_by_vehicle, out_path):
    fig, (ax, ax2) = plt.subplots(2, 1, figsize=(10, 12), gridspec_kw={"height_ratios": [2, 1]})
    all_voxels = union_points(voxels_by_vehicle)
    if all_voxels:
        xs = [p[0] for p in all_voxels]
        ys = [p[1] for p in all_voxels]
        ax.scatter(xs, ys, s=0.25, c="#222222", alpha=0.45, label="occupied voxels")
    for name, pts in trajectories.items():
        if not pts:
            continue
        color = VEHICLE_COLORS.get(name, "#666666")
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        ax.plot(xs, ys, lw=1.8, color=color, label=name)
        ax.scatter(xs[0], ys[0], s=120, marker="*", color=color, edgecolor="black", zorder=4)
        ax.scatter(xs[-1], ys[-1], s=52, marker="o", color=color, edgecolor="black", zorder=4)
    ax.set_aspect("equal")
    ax.set_xlim(box_min[0] - 0.5, box_max[0] + 0.5)
    ax.set_ylim(box_min[1] - 0.5, box_max[1] + 0.5)
    ax.grid(True, ls=":", alpha=0.35)
    ax.set_xlabel("x (m)")
    ax.set_ylabel("y (m)")
    ax.set_title(f"{runroot.name} — coverage")
    ax.legend(loc="upper right", fontsize=8)

    # Lower panel: per-vehicle cumulative unique coverage sequence + fleet union.
    fleet_union_t = []
    fleet_union_n = []
    for name, seq in seq_by_vehicle.items():
        if not seq:
            continue
        color = VEHICLE_COLORS.get(name, "#666666")
        ts = [p[0] for p in seq]
        ns = [p[1] for p in seq]
        ax2.plot(ts, ns, color=color, lw=1.8, alpha=1.0,
                 label=f"{name} coverage", zorder=10)
        if len(ts) > len(fleet_union_t):
            fleet_union_t = ts
            fleet_union_n = ns
    if fleet_union_t:
        ax2.plot(fleet_union_t, fleet_union_n, color="black", lw=0.8,
                 ls="--", alpha=0.25, label="fleet union", zorder=5)
    ax2.set_xlabel("sim time (s)")
    ax2.set_ylabel("unique coverage voxels")
    ax2.set_title("coverage growth")
    ax2.grid(True, ls=":", alpha=0.35)
    ax2.legend(loc="lower right", fontsize=8)
    fig.tight_layout()
    fig.savefig(out_path, dpi=140)
    plt.close(fig)


def plot_grid_map(runroot, box_min, box_max, voxels_by_vehicle, out_path):
    all_voxels = union_points(voxels_by_vehicle)
    grid = rasterize(all_voxels, box_min, box_max, GRID_RES)
    fig, ax = plt.subplots(figsize=(10, 10))
    ax.imshow(np.flipud(grid), cmap="gray", vmin=0, vmax=255,
              extent=[box_min[0], box_max[0], box_min[1], box_max[1]])
    ax.set_aspect("equal")
    ax.set_xlabel("x (m)")
    ax.set_ylabel("y (m)")
    ax.set_title(f"{runroot.name} — grid map")
    fig.tight_layout()
    fig.savefig(out_path, dpi=140)
    plt.close(fig)


def plot_point_cloud(runroot, box_min, box_max, trajectories, voxels_by_vehicle, out_path):
    fig, ax = plt.subplots(figsize=(10, 10))
    all_voxels = union_points(voxels_by_vehicle)
    if all_voxels:
        xs = [p[0] for p in all_voxels]
        ys = [p[1] for p in all_voxels]
        ax.scatter(xs, ys, s=0.25, c="#222222", alpha=0.45, label="occupied voxels")
    for name, pts in trajectories.items():
        if not pts:
            continue
        color = VEHICLE_COLORS.get(name, "#666666")
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        ax.plot(xs, ys, lw=1.8, color=color, label=name)
        ax.scatter(xs[0], ys[0], s=120, marker="*", color=color, edgecolor="black", zorder=4)
        ax.scatter(xs[-1], ys[-1], s=52, marker="o", color=color, edgecolor="black", zorder=4)
    ax.set_aspect("equal")
    ax.set_xlim(box_min[0] - 0.5, box_max[0] + 0.5)
    ax.set_ylim(box_min[1] - 0.5, box_max[1] + 0.5)
    ax.grid(True, ls=":", alpha=0.35)
    ax.set_xlabel("x (m)")
    ax.set_ylabel("y (m)")
    ax.set_title(f"{runroot.name} — point cloud")
    ax.legend(loc="upper right", fontsize=8)
    fig.tight_layout()
    fig.savefig(out_path, dpi=140)
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--runroot", required=True, type=Path)
    parser.add_argument("--world", type=Path, default=DEFAULT_WORLD)
    args = parser.parse_args()

    box_min = (-24.5, -24.5, 0.0)
    box_max = (24.5, 24.5, 3.0)
    trajectories = load_telemetry(args.runroot)
    voxels_by_vehicle = load_coverage_voxels(args.runroot)
    seq_by_vehicle = load_coverage_seq(args.runroot)

    if not voxels_by_vehicle:
        # Fallback only; normal multi-UAV runs should always have observed voxels.
        truth = world_obstacle_voxels(args.world, box_min, box_max)
        voxels_by_vehicle = {"world": truth}
        if not seq_by_vehicle:
            seq_by_vehicle = {"world": []}

    plot_coverage(args.runroot, box_min, box_max, trajectories,
                  voxels_by_vehicle, seq_by_vehicle, args.runroot / "coverage.png")
    plot_grid_map(args.runroot, box_min, box_max, voxels_by_vehicle,
                  args.runroot / "grid_map.png")
    plot_point_cloud(args.runroot, box_min, box_max, trajectories, voxels_by_vehicle,
                     args.runroot / "point_cloud.png")
    print("wrote", args.runroot / "coverage.png")
    print("wrote", args.runroot / "grid_map.png")
    print("wrote", args.runroot / "point_cloud.png")


if __name__ == "__main__":
    main()
