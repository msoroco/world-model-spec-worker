"""Validate the six-case canonical proposal against the active manifest."""

import json
import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
if not os.environ.get("SCENARIO_PIPELINE_OUTPUT_ROOT"):
    raise RuntimeError("Set SCENARIO_PIPELINE_OUTPUT_ROOT under .runtime-work first")
sys.path.insert(0, str((ROOT.parents[1] / "runtime/scenario_pipeline").resolve()))

from worker_exchange.semantic_delivery import validate  # noqa: E402


def main():
    assignment = json.loads((ROOT.parents[1] / "inputs" / ROOT.name / "assignment.json").read_text())
    active = json.loads((ROOT / "execution-manifest.json").read_text())
    assert len(active["cases"]) == 6
    print(json.dumps(validate(ROOT, assignment, active), indent=2))


if __name__ == "__main__":
    main()
