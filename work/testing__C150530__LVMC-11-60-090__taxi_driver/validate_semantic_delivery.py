"""Run the pinned full semantic-delivery validator for the three draft cases."""
from __future__ import annotations

import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = os.environ.get("SCENARIO_PIPELINE_OUTPUT_ROOT", "")
if not OUTPUT or not Path(OUTPUT).resolve().is_relative_to(ROOT / ".runtime-work"):
    raise ValueError("export SCENARIO_PIPELINE_OUTPUT_ROOT under .runtime-work first")
sys.path.insert(0, str(ROOT / "runtime" / "scenario_pipeline"))
from worker_exchange.semantic_delivery import validate  # noqa: E402

ASSIGNMENT = "testing__C150530__LVMC-11-60-090__taxi_driver"
FOLDER = ROOT / "work" / ASSIGNMENT


def main() -> None:
    assignment = json.loads((ROOT / "inputs" / ASSIGNMENT / "assignment.json").read_text())
    manifest = json.loads((FOLDER / "execution-manifest.draft.json").read_text())
    print(json.dumps(validate(FOLDER, assignment, manifest), sort_keys=True))


if __name__ == "__main__":
    main()
