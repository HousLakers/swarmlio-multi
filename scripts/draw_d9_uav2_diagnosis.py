#!/usr/bin/env python3
"""D9 uav2 freeze diagnosis map: world obstacles + 3-UAV trajectories + spawn/inflated marks."""
import json
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, Circle, Wedge
import matplotlib.font_manager as fm

base = "results/RUN-20260823T153614Z-3uav-smoke"

# ---------- obstacles from 2uav_outdoor_50x50_v1.world ----------
rects = []  # (cx, cy, w, h, label)
# boundary walls (0.5 thick, centered)
rects += [(-24.75, 0, 0.5, 50), (24.75, 0, 0.5, 50), (0, -24.75, 50, 0.5), (0, 24.75, 50, 0.5)]
# buildings
rects += [(-15, -14, 8, 6), (14, -14, 7, 8), (-15, 14, 7, 8), (15, 14, 8, 6)]
# split walls
rects += [(-7, 7.5, 0.4, 9), (-7, -7.5, 0.4, 9), (7, 7.5, 0.4, 9), (7, -7.5, 0.4, 9)]
rects += [(-9, 7, 4, 0.4), (9, 7, 4, 0.4), (-9, -7, 4, 0.4), (9, -7, 4, 0.4)]
cols = [(-20, -3), (-19, 5), (20, -4), (19, 5)]  # cylinders r=0.8

fig, ax = plt.subplots(figsize=(11, 11))

for cx, cy, w, h in rects:
    ax.add_patch(Rectangle((cx - w / 2, cy - h / 2), w, h, fc="#9aa5ad", ec="#4b5563", lw=0.6))
for cx, cy in cols:
    ax.add_patch(Circle((cx, cy), 0.8, fc="#9aa5ad", ec="#4b5563", lw=0.6))

# ---------- trajectories ----------
styles = {"uav0": ("#1f77b4", "uav0 (alive, 72.9 m)", 2.0),
          "uav1": ("#2ca02c", "uav1 (dropped @86.7s)", 2.0),
          "uav2": ("#d62728", "uav2 (frozen)", 2.0)}
spawn = {"uav0": (0.0, 0.0), "uav1": (1.5, 0.0), "uav2": (-3.0, 3.0)}
for u in ["uav0", "uav1", "uav2"]:
    xs, ys = [], []
    for line in open(f"{base}/{u}/telemetry.jsonl"):
        d = json.loads(line)
        p = d.get("position")
        if p:
            xs.append(p[0]); ys.append(p[1])
    color, label, lw = styles[u]
    ax.plot(xs, ys, color=color, lw=lw, label=label, alpha=0.9)
    sx, sy = spawn[u]
    ax.plot(sx, sy, marker="*", ms=16, mfc=color, mec="k", mew=1)
    ax.annotate(f"{u} spawn ({sx}, {sy})", (sx, sy), textcoords="offset points",
                xytext=(8, 8), fontsize=9, color=color, fontweight="bold")

# ---------- uav2 inflated occupancy zone ----------
# RACER inflates occupied cells by obstacles_inflation (0.35 m).
# uav2 vehicle start was judged "inside inflated occupancy" the whole run,
# so A* returned NO_PATH -> planner_fail -> stuck in PLAN_TRAJ.
ux, uy = -3.0, 3.0
inflated_radius = 0.35
for col in cols:
    d2 = (col[0] - ux) ** 2 + (col[1] - uy) ** 2
    if d2 < (3.5 + inflated_radius) ** 2:
        ax.add_patch(Circle((col[0], col[1]), inflated_radius, fc="none", ec="#f97316",
                            ls="--", lw=1.4))
for cx, cy, w, h in rects:
    hx, hy = w / 2 + inflated_radius, h / 2 + inflated_radius
    if abs(cx - ux) <= hx and abs(cy - uy) <= hy:
        ax.add_patch(Rectangle((cx - w / 2 - inflated_radius, cy - h / 2 - inflated_radius),
                               w + 2 * inflated_radius, h + 2 * inflated_radius,
                               fc="none", ec="#f97316", ls="--", lw=1.4))

ax.add_patch(Wedge((ux, uy), 1.1, 0, 360, fc="#d62728", alpha=0.08))
ax.annotate("uav2 start inside\ninflated occupancy\n(A* NO_PATH x115k)",
            (ux, uy), textcoords="offset points", xytext=(-95, -60),
            fontsize=10, color="#d62728", fontweight="bold",
            arrowprops=dict(arrowstyle="->", color="#d62728", lw=1.2))

ax.set_xlim(-25.5, 25.5)
ax.set_ylim(-25.5, 25.5)
ax.set_aspect("equal")
ax.grid(True, ls=":", alpha=0.4)
ax.set_xlabel("x (m)")
ax.set_ylabel("y (m)")
ax.set_title("RUN-20260823T153614Z-3uav-smoke — uav2 freeze diagnosis\n"
             "planner stuck in PLAN_TRAJ: A* start inside inflated occupancy (obstacles_inflation=0.35 m)")
ax.legend(loc="upper left", fontsize=9)
fig.tight_layout()
out = f"{base}/uav2_freeze_diagnosis.png"
fig.savefig(out, dpi=130)
print("saved:", out)
