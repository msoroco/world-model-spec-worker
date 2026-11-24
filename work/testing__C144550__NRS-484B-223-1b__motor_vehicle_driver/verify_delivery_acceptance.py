"""Verify all exact selected delivery contracts with the pinned CPU validator."""

import json
import os
import sys
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
output = os.environ.get("SCENARIO_PIPELINE_OUTPUT_ROOT")
if not output or not Path(output).resolve().is_relative_to(ROOT / ".runtime-work"):
    raise ValueError("Set SCENARIO_PIPELINE_OUTPUT_ROOT under .runtime-work")
sys.path.insert(0, str(ROOT / "runtime/scenario_pipeline"))
from worker_exchange.delivery_handoff import validate_case  # noqa: E402


for entry in json.loads((HERE / "execution-manifest.json").read_text())["cases"]:
    validate_case(HERE, entry, expected_sets=["demo-test", "full-test"])
    print("PASS", entry["case_id"])
print("All 11 exact delivery contracts validated")
