"""Validate the current selected C104538 package against the pinned runtime."""
import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
OUTPUT_ROOT=REPO/'.runtime-work'/'c104538-direct-validation-runtime-output'
if not os.environ.get('SCENARIO_PIPELINE_OUTPUT_ROOT') or Path(os.environ['SCENARIO_PIPELINE_OUTPUT_ROOT']).resolve()!=OUTPUT_ROOT.resolve():
    raise RuntimeError('Export SCENARIO_PIPELINE_OUTPUT_ROOT='+str(OUTPUT_ROOT)+' before runtime imports')
sys.path.insert(0, str(REPO / "runtime/pipeline"))
sys.path.insert(0, str(REPO / "runtime/pipeline/scenario_pipeline"))

from scenario_pipeline.worker_exchange.execution_manifest import validate as validate_manifest
from scenario_pipeline.worker_exchange.semantic_delivery import validate as validate_semantic
from scenario_pipeline.worker_exchange.delivery_handoff import validate_case
from scenario_pipeline.worker_exchange.package_compatibility import check_receipts


def main():
    manifest = validate_manifest(REPO, HERE.name)
    assignment = json.loads((REPO / "inputs" / HERE.name / "assignment.json").read_text())
    semantic = validate_semantic(HERE, assignment, manifest)
    for case in manifest["cases"]:
        validate_case(HERE, case, assignment.get("selection_targets"))
    if check_receipts(REPO, HERE, manifest) is not True:
        raise ValueError("Current selected receipts did not pass")
    print(json.dumps({"passed": True, "cases": len(manifest["cases"]),
                      "semantic": semantic, "delivery_handoffs": len(manifest["cases"]),
                      "compatibility_receipts": 12}))


if __name__ == "__main__":
    main()
