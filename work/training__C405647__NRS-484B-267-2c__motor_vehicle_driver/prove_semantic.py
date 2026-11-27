"""Validate the draft canonical stages against the active runtime contracts."""

import json
import os
from pathlib import Path
import sys


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
output = Path(os.environ.get("SCENARIO_PIPELINE_OUTPUT_ROOT", "")).resolve()
if not output.is_relative_to((ROOT / ".runtime-work").resolve()):
    raise ValueError("Export SCENARIO_PIPELINE_OUTPUT_ROOT under .runtime-work first")
sys.path[:0] = [str(ROOT / "runtime"), str(ROOT / "runtime/scenario_pipeline")]
from scenario_pipeline.worker_exchange.semantic_delivery import validate  # noqa: E402


def main():
    assignment = json.loads((ROOT / "inputs" / HERE.name / "assignment.json").read_text())
    manifest = json.loads((HERE / "draft-native-manifest.json").read_text())
    result = validate(HERE, assignment, manifest)
    if result["selected_cases"] != 2 or result["stage_count"] != 12:
        raise ValueError("Selected draft semantic cases or stage chain changed")
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
