"""Replay all exact construction, fallback, physical and semantic gates."""

import json
import os
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def main():
    output = os.environ.get("SCENARIO_PIPELINE_OUTPUT_ROOT", "")
    if not output or not Path(output).resolve().is_relative_to(ROOT / ".runtime-work"):
        raise ValueError("Set SCENARIO_PIPELINE_OUTPUT_ROOT under .runtime-work")
    from scenario_pipeline.worker_exchange.execution_manifest import validate
    from scenario_pipeline.worker_exchange.semantic_delivery import validate as semantic

    manifest = validate(ROOT, HERE.name)
    assignment = json.loads((ROOT / "inputs" / HERE.name / "assignment.json").read_text())
    semantic(HERE, assignment, manifest)
    print(json.dumps({"selected_execution_passed": True,
                      "semantic_delivery_passed": True,
                      "exact_cases": len(manifest["cases"])}))


if __name__ == "__main__":
    main()
