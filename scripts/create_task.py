#!/usr/bin/env python3
import json, sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ROLES = {"two-uav-smoke":"experiment", "diagnose-telemetry":"code", "make-report":"report"}
if len(sys.argv) != 2 or sys.argv[1] not in ROLES:
    raise SystemExit("usage: create_task.py two-uav-smoke|diagnose-telemetry|make-report")
kind = sys.argv[1]
task_id = "TASK-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + kind
task = {"task_id":task_id,"kind":kind,"role":ROLES[kind],"status":"queued",
        "read":["AGENTS.md","state/current_summary.md"],
        "write":[f"tasks/{task_id}.result.json","state/events.jsonl"],
        "forbidden":["modify_src","expand_experiment_scope","arbitrary_shell"]}
(ROOT/"tasks").mkdir(exist_ok=True)
(ROOT/"tasks"/f"{task_id}.json").write_text(json.dumps(task,ensure_ascii=False,indent=2)+"\n")
with (ROOT/"state/task_queue.jsonl").open("a") as f: f.write(json.dumps(task,ensure_ascii=False)+"\n")
print(ROOT/"tasks"/f"{task_id}.json")
