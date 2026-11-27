"""Validate eight exact execution, semantic and handoff contracts."""

import json
import os
from pathlib import Path
import sys


HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]


def run():
    output_root = Path(os.environ["SCENARIO_PIPELINE_OUTPUT_ROOT"]).resolve()
    if REPO / ".runtime-work" not in output_root.parents:
        raise ValueError("Runtime output root must be under .runtime-work")
    sys.path.insert(0, str(REPO / "runtime/scenario_pipeline"))
    from worker_exchange.execution_manifest import validate
    from worker_exchange.semantic_delivery import validate as semantic
    from worker_exchange.delivery_handoff import validate_case

    manifest = validate(REPO, HERE.name)
    assignment = json.loads((REPO / "inputs" / HERE.name / "assignment.json").read_text())
    semantic_result = semantic(HERE, assignment, manifest)
    for entry in manifest["cases"]:
        validate_case(HERE, entry, assignment.get("selection_targets"))
    return {"exact_cases": len(manifest["cases"]),
            "semantic_stages": semantic_result["stage_count"],
            "delivery_handoffs": len(manifest["cases"])}


if __name__ == "__main__":
    print(json.dumps(run(), sort_keys=True))
