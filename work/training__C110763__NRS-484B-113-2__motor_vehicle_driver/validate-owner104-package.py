"""Validate the selected current-runtime CPU package without CARLA."""
import json
from pathlib import Path
import sys


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "runtime/scenario_pipeline"))

from worker_exchange import delivery_handoff, execution_manifest, package_compatibility, semantic_delivery


def main():
    assignment = json.loads((ROOT / "inputs" / HERE.name / "assignment.json").read_text())
    manifest = execution_manifest.validate(ROOT, HERE.name)
    print("execution_manifest passed")
    semantic = semantic_delivery.validate(HERE, assignment, manifest)
    print("semantic", semantic)
    for entry in manifest["cases"]:
        delivery_handoff.validate_case(HERE, entry, assignment["selection_targets"])
        print("delivery", entry["case_id"], "passed")
    package_compatibility.check_receipts(ROOT, HERE, manifest)
    print("compatibility and all passed")


if __name__ == "__main__":
    main()
