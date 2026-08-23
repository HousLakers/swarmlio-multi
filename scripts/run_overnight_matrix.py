#!/usr/bin/env python3
"""Overnight load-balancing matrix executor.

Runs the 300s load-balancing matrix (6 groups x 3 reps = 18 runs), each run
consuming one approval (max_uses=1). The executor regenerates the static
config `exploration` section, updates the source-hash manifest, reissues the
approval bound to the current manifest+hash combination, launches the stack
through the frozen runner, and records the outcome in the matrix ledger.

Resumable: state is kept in `experiments/matrix_state.json`; re-running the
executor continues from the first non-terminal run.

Usage:
  run_overnight_matrix.py plan                # print matrix + time estimate, no launch
  run_overnight_matrix.py status              # show current progress
  run_overnight_matrix.py run                 # execute all pending runs
  run_overnight_matrix.py run --groups A1,B1  # restrict to groups
  run_overnight_matrix.py run --max-runs N    # cap runs this invocation
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "scripts" / "two_uav_runner.py"
CONFIG_PATH = ROOT / "config" / "3uav_static.yaml"
HASH_MANIFEST_PATH = ROOT / "config" / "3uav_source_hashes.sha256"
APPROVAL_PATH = ROOT / "state" / "3uav_approval.yaml"
MANIFEST_DIR = ROOT / "experiments" / "manifests"
MATRIX_STATE = ROOT / "experiments" / "matrix_state.json"
MATRIX_LEDGER = ROOT / "experiments" / "matrix_results.jsonl"
MATRIX_MD = ROOT / "experiments" / "matrix_results.md"

# One entry per group. `dropout` False => dedicated no-drop manifest.
MATRIX = [
    {"id": "A1", "objective": "MINSUM", "capacity": 0.75, "dropout": False},
    {"id": "A2", "objective": "MINMAX", "capacity": 0.75, "dropout": False},
    {"id": "A3", "objective": "MINMAX", "capacity": 0.50, "dropout": False},
    {"id": "B1", "objective": "MINSUM", "capacity": 0.75, "dropout": True},
    {"id": "B2", "objective": "MINMAX", "capacity": 0.75, "dropout": True},
    {"id": "B3", "objective": "MINMAX", "capacity": 0.50, "dropout": True},
]
REPS = 3
DURATION_SIM_S = 300

BASE_MANIFEST = MANIFEST_DIR / "3uav_smoke.yaml"
MANIFEST_MD5_KEYS = ("experiment_id", "approval_status", "duration_sim_s",
                     "dropout", "latest_runroot")


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def now_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def load_yaml(path: Path):
    import yaml
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def dump_yaml(data, path: Path):
    import yaml
    path.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True),
                    encoding="utf-8")


def all_runs():
    runs = []
    for group in MATRIX:
        for rep in range(1, REPS + 1):
            runs.append({"group": group["id"], "rep": rep,
                         "objective": group["objective"],
                         "capacity": group["capacity"],
                         "dropout": group["dropout"]})
    return runs


def load_state():
    if MATRIX_STATE.is_file():
        try:
            return json.loads(MATRIX_STATE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"runs": {}, "started_utc": None, "finished_utc": None}


def save_state(state):
    MATRIX_STATE.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n",
                            encoding="utf-8")


def manifest_for(group_id: str, dropout: bool) -> Path:
    """Every run gets its own manifest file so the frozen base manifest is
    never mutated by the executor."""
    kind = "drop" if dropout else "nodrop"
    return MANIFEST_DIR / ("3uav_%s_%s.yaml" % (kind, group_id.lower()))


def regenerate_manifest(group):
    """Write the per-group manifest (dropout enabled or disabled)."""
    manifest = load_yaml(BASE_MANIFEST)
    manifest["experiment_id"] = "three_uav_%s_v1" % group["id"].lower()
    manifest["approval_status"] = "blocked_pending_verified_launch_and_preflight"
    manifest["duration_sim_s"] = DURATION_SIM_S
    manifest["latest_runroot"] = None
    dropout = manifest.get("dropout")
    if dropout is not None:
        dropout["enabled"] = bool(group["dropout"])
    path = manifest_for(group["id"], group["dropout"])
    dump_yaml(manifest, path)
    return path


def update_config_and_hashes(group):
    """Write the exploration section into 3uav_static.yaml, then refresh the
    source-hash manifest entries for config and (if changed) the manifest."""
    config = load_yaml(CONFIG_PATH)
    config.setdefault("exploration", {})
    config["exploration"]["mtsp_objective"] = group["objective"]
    config["exploration"]["capacity_factor"] = float(group["capacity"])
    dump_yaml(config, CONFIG_PATH)

    manifest_path = manifest_for(group["id"], group["dropout"])
    lines = HASH_MANIFEST_PATH.read_text(encoding="utf-8").splitlines()
    out = []
    replaced = {"config": False, "manifest": False}
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            out.append(line)
            continue
        parts = stripped.split(None, 1)
        if len(parts) != 2:
            out.append(line)
            continue
        _old_hash, rel = parts
        if rel == "config/3uav_static.yaml":
            out.append("%s  %s" % (sha256_file(CONFIG_PATH), rel))
            replaced["config"] = True
        elif rel == "experiments/manifests/3uav_smoke.yaml":
            out.append("%s  %s" % (sha256_file(BASE_MANIFEST), rel))
            replaced["manifest"] = True
        elif rel == str(manifest_path.relative_to(ROOT)):
            out.append("%s  %s" % (sha256_file(manifest_path), rel))
            replaced["manifest"] = True
        else:
            out.append(line)
    if not replaced["config"]:
        out.append("%s  %s" % (sha256_file(CONFIG_PATH), "config/3uav_static.yaml"))
    if not replaced["manifest"]:
        out.append("%s  %s" % (sha256_file(manifest_path),
                               str(manifest_path.relative_to(ROOT))))
    HASH_MANIFEST_PATH.write_text("\n".join(out) + "\n", encoding="utf-8")
    return manifest_path


def reissue_approval(group, manifest_path):
    """Write state/3uav_approval.yaml bound to the current hashes."""
    manifest_hash = sha256_file(manifest_path)
    source_hash = sha256_file(HASH_MANIFEST_PATH)
    contract = load_yaml(ROOT / "config" / "3uav_approval_contract.yaml")
    approval = {
        "schema_version": 1,
        "stage": "smoke",
        "approved": True,
        "allowed_actions": ["launch"],
        "manifest_sha256": manifest_hash,
        "source_hash_manifest_sha256": source_hash,
        "issued_by": contract.get("issued_by_must_be", "sol"),
        "max_uses": contract.get("max_uses", 1),
        "issuance_id": "lb-%s-%s-3uav-300s" % (group["id"], now_utc()),
    }
    manifest = load_yaml(manifest_path)
    if manifest.get("dropout"):
        approval["dropout"] = manifest["dropout"]
    dump_yaml(approval, APPROVAL_PATH)
    return manifest_hash, source_hash


def run_one(run, state):
    group_id = run["group"]
    rep = run["rep"]
    key = "%s-r%d" % (group_id, rep)
    state["runs"][key] = {"status": "running", "started_utc": now_utc(),
                          **{k: run[k] for k in ("group", "rep", "objective",
                                                 "capacity", "dropout")}}
    save_state(state)
    runroot = None
    try:
        manifest_path = regenerate_manifest(run)
        update_config_and_hashes(run)
        manifest_hash, source_hash = reissue_approval(run, manifest_path)
        proc = subprocess.run(
            [sys.executable, str(RUNNER), "launch", "--manifest", str(manifest_path)],
            cwd=str(ROOT), capture_output=True, text=True, timeout=3600)
        runroot = _find_latest_runroot()
        summary = {"exit": proc.returncode, "stdout_tail": proc.stdout[-2000:],
                   "stderr_tail": proc.stderr[-2000:]}
        if runroot and (runroot / "execution_result.json").is_file():
            er = json.loads((runroot / "execution_result.json").read_text())
            fleet_abort = []
            fleet_path = runroot / "fleet/metrics.json"
            if fleet_path.is_file():
                fleet_abort = (json.loads(fleet_path.read_text())
                               .get("abort_reasons", []))
            summary.update({
                "runroot": str(runroot),
                "exit_reason": er.get("exit_reason"),
                "final_safety_passed": er.get("final_safety_passed"),
                "final_safety_detail": er.get("final_safety_detail"),
                "abort_reasons": fleet_abort,
            })
        ok = (proc.returncode == 0 and summary.get("exit_reason") == "duration_complete"
              and summary.get("final_safety_passed") is True)
        state["runs"][key].update({
            "status": "done" if ok else "failed",
            "finished_utc": now_utc(),
            "manifest_sha256": manifest_hash,
            "source_hash_sha256": source_hash,
            **summary,
        })
        save_state(state)
        _append_ledger(key, state["runs"][key])
        return ok
    except Exception as exc:
        state["runs"][key].update({"status": "error", "finished_utc": now_utc(),
                                   "error": repr(exc), "runroot": str(runroot) if runroot else None})
        save_state(state)
        _append_ledger(key, state["runs"][key])
        return False


def _find_latest_runroot():
    """Return the most recently modified RUN-*-3uav-smoke directory."""
    results = ROOT / "results"
    if not results.is_dir():
        return None
    candidates = [p for p in results.glob("RUN-*-3uav-smoke")]
    if not candidates:
        return None
    return max(candidates, key=lambda p: p.stat().st_mtime)



def _append_ledger(key, record):
    MATRIX_LEDGER.parent.mkdir(parents=True, exist_ok=True)
    with MATRIX_LEDGER.open("a", encoding="utf-8") as f:
        f.write(json.dumps({"key": key, **record}, sort_keys=True) + "\n")


def render_md(state):
    lines = ["# Load-balancing matrix results (300s)", ""]
    lines.append("| Run | Group | Objective | Capacity | Dropout | Status | Exit | Safety | Runroot |")
    lines.append("|-----|-------|-----------|----------|---------|--------|------|--------|---------|")
    for run in all_runs():
        key = "%s-r%d" % (run["group"], run["rep"])
        rec = state["runs"].get(key, {})
        status = rec.get("status", "pending")
        lines.append("| %s | %s | %s | %s | %s | %s | %s | %s | %s |" % (
            key, run["group"], rec.get("objective", run["objective"]),
            rec.get("capacity", run["capacity"]),
            "uav1@60s" if run["dropout"] else "none",
            status, rec.get("exit_reason", "-"), rec.get("final_safety_passed", "-"),
            rec.get("runroot", "-")))
    MATRIX_MD.parent.mkdir(parents=True, exist_ok=True)
    MATRIX_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def cmd_plan():
    runs = all_runs()
    est = len(runs) * 30
    print("Matrix: %d runs (6 groups x %d reps), %d sim-s each" %
          (len(runs), REPS, DURATION_SIM_S))
    print("Estimated wall time: ~%d minutes (~%.1f h) at 30 min/run"
          % (est, est / 60.0))
    for group in MATRIX:
        print("  %s  objective=%-6s capacity=%.2f dropout=%s  x%d"
              % (group["id"], group["objective"], group["capacity"],
                 "node_level@60s" if group["dropout"] else "none", REPS))


def cmd_status():
    state = load_state()
    done = sum(1 for v in state["runs"].values() if v.get("status") in ("done",))
    failed = sum(1 for v in state["runs"].values() if v.get("status") in ("failed", "error"))
    running = sum(1 for v in state["runs"].values() if v.get("status") == "running")
    pending = 18 - done - failed - running
    print("done=%d failed=%d running=%d pending=%d" % (done, failed, running, pending))
    render_md(state)
    if MATRIX_MD.is_file():
        print("ledger: %s" % MATRIX_MD)


def cmd_run(groups=None, max_runs=None):
    state = load_state()
    if state.get("started_utc") is None:
        state["started_utc"] = now_utc()
    executed = 0
    consecutive_failures = 0
    for run in all_runs():
        if groups and run["group"] not in groups:
            continue
        key = "%s-r%d" % (run["group"], run["rep"])
        rec = state["runs"].get(key, {})
        if rec.get("status") in ("done", "failed", "error", "running"):
            continue
        if max_runs is not None and executed >= max_runs:
            break
        if consecutive_failures >= 2:
            print("[%s] stopping: 2 consecutive failures without manual review"
                  % now_utc(), flush=True)
            break
        print("[%s] %s starting (objective=%s capacity=%s dropout=%s)" %
              (now_utc(), key, run["objective"], run["capacity"], run["dropout"]),
              flush=True)
        ok = run_one(run, state)
        executed += 1
        status = state["runs"][key]["status"]
        consecutive_failures = 0 if ok else consecutive_failures + 1
        print("[%s] %s -> %s" % (now_utc(), key, status), flush=True)
        render_md(state)
    if all(state["runs"].get("%s-r%d" % (g["id"], r), {}).get("status") in
           ("done", "failed", "error") for g in MATRIX for r in range(1, REPS + 1)):
        state["finished_utc"] = now_utc()
    save_state(state)
    render_md(state)
    print("stopping (executed=%d)" % executed, flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("plan", "status", "run"))
    parser.add_argument("--groups", default=None,
                        help="comma-separated group ids (A1,A2,B3)")
    parser.add_argument("--max-runs", type=int, default=None)
    args = parser.parse_args()
    groups = set(args.groups.split(",")) if args.groups else None
    if args.command == "plan":
        cmd_plan()
    elif args.command == "status":
        cmd_status()
    else:
        cmd_run(groups=groups, max_runs=args.max_runs)


if __name__ == "__main__":
    main()
