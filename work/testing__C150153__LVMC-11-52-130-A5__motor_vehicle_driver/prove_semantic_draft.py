"""Validate canonical semantic stages against a scratch description mirror.

The mirror tests stage schemas and exact case coverage only. It is not a
selected execution manifest and carries no offline or physical proof.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import sys


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def prove(scratch: Path) -> dict:
    scratch = Path(scratch).resolve()
    allowed = (ROOT / ".runtime-work").resolve()
    pipeline_output = Path(os.environ.get("SCENARIO_PIPELINE_OUTPUT_ROOT", "")).resolve()
    if not scratch.is_relative_to(allowed) or not pipeline_output.is_relative_to(allowed):
        raise ValueError("semantic scratch and pipeline output must be under .runtime-work")
    if scratch.exists():
        raise ValueError("semantic scratch already exists")
    (scratch / "proposals").mkdir(parents=True)
    for path in (HERE / "proposals").glob("*.json"):
        shutil.copy2(path, scratch / "proposals" / path.name)
    cases = json.loads((HERE / "proposals/cases.json").read_text())["cases"]
    selected = [case for case in cases if case["target_type"] != "baseline"]
    manifest = {"cases": []}
    for index, case in enumerate(selected):
        relative = f"case-{index}.json"
        (scratch / relative).write_text(json.dumps(
            {"recording_description": case["recording_description"]}) + "\n")
        manifest["cases"].append({"case_id": case["case_id"], "construction": relative})
    assignment = json.loads((ROOT / "inputs" / HERE.name / "assignment.json").read_text())
    sys.path.insert(0, str(ROOT / "runtime"))
    sys.path.insert(0, str(ROOT / "runtime/scenario_pipeline"))
    from scenario_pipeline.worker_exchange.semantic_delivery import validate
    return validate(scratch, assignment, manifest)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--scratch", type=Path, required=True)
    arguments = parser.parse_args()
    print(json.dumps(prove(arguments.scratch), indent=2))
