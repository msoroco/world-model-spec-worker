"""Replay selected C144550 semantic coverage under the pinned CPU runtime."""

import json
import os
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def main():
    output = os.environ.get("SCENARIO_PIPELINE_OUTPUT_ROOT", "")
    if not output or not Path(output).resolve().is_relative_to(ROOT / ".runtime-work"):
        raise ValueError("Set SCENARIO_PIPELINE_OUTPUT_ROOT under .runtime-work")
    from scenario_pipeline.worker_exchange.semantic_delivery import validate

    assignment = json.loads((ROOT / "inputs" / HERE.name / "assignment.json").read_text())
    manifest = json.loads((HERE / "execution-manifest.json").read_text())
    validate(HERE, assignment, manifest)
    cases = [entry["case_id"] for entry in manifest["cases"]]
    if len(cases) != 11 or len(set(cases)) != 11:
        raise ValueError("Expected eleven distinct selected exact cases")
    print(json.dumps({"semantic_delivery_passed": True, "selected_exact_cases": cases}))


if __name__ == "__main__":
    main()
