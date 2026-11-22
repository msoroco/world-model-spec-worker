"""Validate the exact worker-authored semantic proposal chain on CPU."""
import json
import os
import sys
from pathlib import Path


HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
output = os.environ.get("SCENARIO_PIPELINE_OUTPUT_ROOT")
if not output or not Path(output).resolve().is_relative_to(REPO / ".runtime-work"):
    raise ValueError("Set SCENARIO_PIPELINE_OUTPUT_ROOT under .runtime-work")
sys.path.insert(0, str(REPO / "runtime/scenario_pipeline"))
sys.path.insert(1, str(REPO / "runtime/python"))

from worker_exchange.semantic_delivery import validate  # noqa: E402


if __name__ == "__main__":
    assignment = json.loads((REPO / "inputs" / HERE.name / "assignment.json").read_text())
    manifest = json.loads((HERE / "execution-manifest.json").read_text())
    print(json.dumps(validate(HERE, assignment, manifest), indent=2))
