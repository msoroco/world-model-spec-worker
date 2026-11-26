"""Run six saved finalizers on explicit three-frame synthetic source packets."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

from build_construction import ROOT

sys.path.insert(0, str(ROOT / "tests"))
from test_saved_entry import make_attempt, MODULE as saved_module


REPO = ROOT.parents[1]
PRIVATE = REPO / ".runtime-work" / "c227824-saved-synthetic"


def _write(path, value):
    path.write_text(json.dumps(value, indent=2) + "\n")


def _update_attempt(root, case):
    case_id = case["case_id"]
    scene_path = root / "scene.json"
    scene = json.loads(scene_path.read_text())
    scene.update(case_id=case_id, entry_request=case["entry_request"],
                 requested_pedestrian_indication=case["other_device_indication"],
                 speed_mps=case.get("walk_speed_target_mps", 1.0))
    _write(scene_path, scene)
    for name in saved_module.PACKETS:
        path = root / name
        rows = [json.loads(line) for line in path.read_text().splitlines()]
        for row in rows:
            if "case_id" in row:
                row["case_id"] = case_id
            if name == "device-history.jsonl" and case["other_device_indication"] != "none":
                device = {"official": True, "indication": case["other_device_indication"],
                          "head_id": 8, "route_id": scene["route_id"]}
                if case["other_device_indication"] == "flashing_hand_countdown":
                    device["countdown_s"] = 7.0 - row["frame"] * .05
                row["other_devices"] = [device]
            if name == "walker-body-history.jsonl" and case["entry_request"] == "wait":
                row["body_polygon_xy_m"] = [[-2, 3], [-1, 3], [-1, 4], [-2, 4]]
        path.write_text("".join(json.dumps(row) + "\n" for row in rows))
    construction = json.loads((ROOT / "cases" / case_id[len(ROOT.name) + 2:] / "construction.json").read_text())
    _write(root / "construction.json", construction)
    config = json.loads((ROOT / "cases" / case_id[len(ROOT.name) + 2:] / "config.json").read_text())
    _write(root / "config.json", config)
    acquisition = json.loads((root / "acquisition.json").read_text())
    for name in ("scene.json", *saved_module.PACKETS):
        acquisition[name]["sha256"] = hashlib.sha256((root / name).read_bytes()).hexdigest()
    _write(root / "acquisition.json", acquisition)


def _run(root):
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["TMPDIR"] = str(PRIVATE)
    env["SCENARIO_PIPELINE_OUTPUT_ROOT"] = str(PRIVATE / "runtime-output")
    return subprocess.run([sys.executable, str(ROOT / "analysis.py"),
                           "--attempt", str(root),
                           "--output", str(root / "analysis-report.json")],
                          cwd=REPO, env=env, capture_output=True, text=True)


def main():
    PRIVATE.mkdir(parents=True, exist_ok=True)
    plan = json.loads((ROOT / "case-plan.json").read_text())
    rows = []
    for case in plan["cases"]:
        suffix = case["case_id"][len(ROOT.name) + 2:]
        root = PRIVATE / suffix
        if root.exists():
            shutil.rmtree(root)
        root.mkdir()
        make_attempt(root)
        _update_attempt(root, case)
        run = _run(root)
        if run.returncode:
            raise RuntimeError(case["case_id"] + ": " + run.stdout + run.stderr)
        result = json.loads((root / "result.json").read_text())
        report = json.loads((root / "analysis-report.json").read_text())
        if (result["case_id"] != case["case_id"] or
                result["physical_acceptance_claimed"] is not False or
                report["diagnostic_fixture"] is not True):
            raise ValueError("saved diagnostic result changed case or claimed physical acceptance")
        rows.append({"case_id": case["case_id"], "saved_exit_code": 0,
                     "entry_observed": report["measurement"]["entry_observed"],
                     "target_matched": result["target_checks"][0]["matched"],
                     "diagnostic_fixture": True})
    negative = PRIVATE / "missing-device-source"
    if negative.exists():
        shutil.rmtree(negative)
    shutil.copytree(PRIVATE / plan["cases"][0]["case_id"][len(ROOT.name) + 2:], negative)
    (negative / "device-history.jsonl").unlink()
    (negative / "result.json").unlink()
    (negative / "analysis-report.json").unlink()
    rejected = _run(negative)
    if rejected.returncode == 0 or "Missing required source: device-history.jsonl" not in rejected.stderr:
        raise ValueError("missing original device packet not rejected")
    print(json.dumps({"format": "c227824-synthetic-saved-summary", "cases": rows,
                      "missing_device_source_rejected": True,
                      "physical_acceptance_claimed": False}, indent=2))


if __name__ == "__main__":
    main()
