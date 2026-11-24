"""Validate the selected semantic chain against the pinned runtime."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path


def main() -> None:
    folder = Path(__file__).resolve().parent
    repo = folder.parents[1]
    output = os.environ.get("SCENARIO_PIPELINE_OUTPUT_ROOT")
    if not output or not Path(output).resolve().is_relative_to(repo / ".runtime-work"):
        raise ValueError("Set SCENARIO_PIPELINE_OUTPUT_ROOT under .runtime-work")
    sys.path.insert(0, str(repo / "runtime/scenario_pipeline"))
    from worker_exchange.semantic_delivery import validate

    assignment = json.loads((repo / "inputs" / folder.name / "assignment.json").read_text())
    manifest = json.loads((folder / "execution-manifest.json").read_text())
    print(validate(folder, assignment, manifest))
    print("law quote:", assignment["law"]["text"])
    print("selected cases:", [entry["case_id"] for entry in manifest["cases"]])
    plan = json.loads((folder / "case-plan.json").read_text())
    print("comparisons:", [entry["comparison_id"] for entry in plan["comparisons"]])


if __name__ == "__main__":
    main()
