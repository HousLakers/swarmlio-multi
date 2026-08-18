#!/usr/bin/env python3
"""DeepSeek is optional; hard safety rules must remain local and deterministic."""
import argparse, json, os, urllib.request
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
def snapshot():
    return {"state":json.loads((ROOT/"state/current.json").read_text()),"summary":(ROOT/"state/current_summary.md").read_text()}
def ask(data):
    key=os.environ.get("DEEPSEEK_API_KEY")
    if not key: return {"status":"no_api_key","allowed_action":"none"}
    payload={"model":os.environ.get("DEEPSEEK_MODEL","deepseek-v4-flash"),"messages":[
      {"role":"system","content":"Return JSON only. Allowed actions: none, collect_topic_diagnostics, stop_current_slot, mark_uav_failed, continue_experiment. Never invent shell commands or change source/parameters."},
      {"role":"user","content":json.dumps(data,ensure_ascii=False)}],"response_format":{"type":"json_object"},"max_tokens":800}
    req=urllib.request.Request("https://api.deepseek.com/chat/completions",data=json.dumps(payload).encode(),headers={"Authorization":f"Bearer {key}","Content-Type":"application/json"},method="POST")
    with urllib.request.urlopen(req,timeout=30) as r: body=json.loads(r.read())
    return json.loads(body["choices"][0]["message"]["content"])
parser=argparse.ArgumentParser()
parser.add_argument("--once", action="store_true")
parser.parse_args()
data=snapshot()
print(json.dumps({"snapshot":data,"decision":ask(data)},ensure_ascii=False,indent=2))
