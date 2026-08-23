#!/usr/bin/env python3
"""Render 2uav_outdoor_50x50_v1.world top view with spawn points and inflation."""
import xml.etree.ElementTree as ET
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, Circle

BASE = Path("/home/houslakers/auto_tune_racer/racer-platform/environment/worlds")
WORLD = BASE / "2uav_outdoor_50x50_v1.world"
OUT = Path("/home/houslakers/auto_tune_racer/swarmlio_multi/results/map_50x50_overview.png")

root = ET.parse(WORLD).getroot()
fig, ax = plt.subplots(figsize=(10, 10), dpi=150)
fig.patch.set_facecolor("white")
ax.set_facecolor("white")

# Obstacles: fill rectangles/cylinders
for model in root.findall(".//model"):
    name = model.attrib.get("name", "")
    pose = [float(v) for v in (model.findtext("pose") or "0 0 0 0 0 0").split()]
    cx, cy, cz = pose[:3]
    for box in model.findall(".//collision//box"):
        sx, sy, sz = [float(v) for v in box.findtext("size").split()]
        x0, y0 = cx - sx / 2, cy - sy / 2
        ax.add_patch(Rectangle((x0, y0), sx, sy, facecolor="#c0392b", alpha=0.55,
                               edgecolor="#922b21", linewidth=0.8, zorder=3))
        # inflation ring (0.35 m)
        ax.add_patch(Rectangle((x0 - 0.35, y0 - 0.35), sx + 0.7, sy + 0.7,
                               fill=False, edgecolor="#e74c3c", linewidth=0.6,
                               linestyle=(0, (2, 2)), alpha=0.6, zorder=2))
    for cyl in model.findall(".//collision//cylinder"):
        r = float(cyl.findtext("radius"))
        ax.add_patch(Circle((cx, cy), r, facecolor="#c0392b", alpha=0.55,
                            edgecolor="#922b21", linewidth=0.8, zorder=3))
        ax.add_patch(Circle((cx, cy), r + 0.35, fill=False, edgecolor="#e74c3c",
                            linewidth=0.6, linestyle=(0, (2, 2)), alpha=0.6, zorder=2))

# Field boundary (50 x 50) and planner box (49 x 49)
ax.add_patch(Rectangle((-25, -25), 50, 50, fill=False, edgecolor="#222222", linewidth=1.5, zorder=4))
ax.add_patch(Rectangle((-24.5, -24.5), 49, 49, fill=False, edgecolor="#888888",
                       linewidth=1.0, linestyle=(0, (4, 3)), zorder=4))

# Spawn points
spawns = {"uav0": (0.0, 0.0), "uav1": (1.5, 0.0), "uav2": (-3.0, 3.0)}
for label, (x, y) in spawns.items():
    ax.scatter(x, y, s=120, c="#1a5276", marker="o", zorder=6, edgecolor="white", linewidth=1.2)
    ax.annotate(f"{label} ({x:.1f}, {y:.1f})", (x, y), xytext=(8, 8),
                textcoords="offset points", fontsize=11, fontweight="bold",
                color="#1a5276", zorder=6)

# uav2 hover position (from run telemetry)
ax.scatter(-3.09, 3.07, s=140, c="#e67e22", marker="x", linewidth=2.4, zorder=6)
ax.annotate("uav2 hover\n(-3.09, 3.07)", (-3.09, 3.07), xytext=(12, -26),
            textcoords="offset points", fontsize=10, color="#e67e22", zorder=6)

# uav2 inflation footprint radius 0.35 around hover
ax.add_patch(Circle((-3.09, 3.07), 0.35, fill=False, edgecolor="#e67e22",
                    linewidth=1.0, linestyle=(0, (1, 1)), zorder=5))

ax.set_xlim(-26, 26)
ax.set_ylim(-26, 26)
ax.set_aspect("equal", adjustable="box")
ax.set_title("2uav_outdoor_50x50_v1 — obstacles (red), inflation 0.35 m (dashed),\n"
             "planner box ±24.5 (gray dashed), spawn points (blue), uav2 hover (orange x)",
             fontsize=11)
ax.grid(True, linestyle=":", alpha=0.4)
fig.savefig(OUT, dpi=150, facecolor="white", bbox_inches="tight")
plt.close(fig)
print(OUT)
