"""Rebind four selected CPU constructions to the completed source plan."""

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
plan_bytes = (ROOT / "case-plan.json").read_bytes()
plan_sha = hashlib.sha256(plan_bytes).hexdigest()
manifest = json.loads((ROOT / "selected-v2-manifest.json").read_text())


def refresh(reference, label):
    old = json.loads((ROOT / reference).read_text())
    for entry in old["files"]:
        if entry["path"] == "case-plan.json":
            entry["content"] = plan_bytes.decode()
        elif entry["path"] == "config.json":
            config = json.loads(entry["content"])
            config["case_plan_sha256"] = plan_sha
            entry["content"] = json.dumps(config, indent=2, ensure_ascii=False) + "\n"
        elif entry["path"] == "v2_finalize.py":
            source = entry["content"]
            source = source.replace(
                "    result = {'case_id': config['case_id']",
                "    lane_context = root / 'requested-circulating-lane.json'\n"
                "    lane_context.write_text(json.dumps({'requested_circulating_lane': measured['requested_lane_id'], "
                "'source': 'roundabout-track.jsonl', 'provenance_kind': 'synthetic_cpu_source_shaped'}) + '\\n')\n"
                "    result = {'case_id': config['case_id']",
            )
            source = source.replace(
                "'reference': stream.name}],",
                "'reference': stream.name}, {'name': 'requested_circulating_lane', "
                "'unit': 'lane_id', 'reference': lane_context.name}],",
            )
            source = source.replace(
                "'realized_observables': {'authored_lane_id':",
                "'realized_observables': {'requested_circulating_lane': "
                "{'value': measured['requested_lane_id'], 'unit': 'lane_id', "
                "'method': 'saved source-shaped map lane readback', "
                "'time_window': 'full 30 s synthetic diagnostic', "
                "'statistic': 'last', 'reference': lane_context.name}, "
                "'authored_lane_id':",
            )
            assert "lane_context.write_text" in source
            entry["content"] = source
    target = f"selected-v2/constructions/{label}.json"
    path = ROOT / target
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(old, indent=2, ensure_ascii=False) + "\n")
    return target, hashlib.sha256(path.read_bytes()).hexdigest()


for number, case in enumerate(manifest["cases"], 1):
    target, sha = refresh(f"v2-native-draft/witness_{number}-construction.json", f"witness{number}-primary")
    case["construction"] = target
    case["construction_sha256"] = sha
    case["offline"]["construction_sha256"] = sha
    candidate = case["candidates"][0]
    target, sha = refresh(f"v2-fallback-draft/witness_{number}-fallback1-construction.json", f"witness{number}-fallback1")
    candidate["construction"] = target
    candidate["construction_sha256"] = sha
    candidate["offline"]["construction_sha256"] = sha

path = ROOT / "selected-v2-refresh-manifest.json"
path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")
print("plan", plan_sha)
print("refresh_manifest", hashlib.sha256(path.read_bytes()).hexdigest())
