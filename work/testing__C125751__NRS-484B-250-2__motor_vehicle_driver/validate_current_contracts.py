"""Pinned static validation of the refreshed exact C125751 delivery package."""
import json
from pathlib import Path

from worker_exchange.execution_manifest import validate as validate_execution
from worker_exchange.package_compatibility import check_receipts
from worker_exchange.semantic_delivery import validate as validate_semantic
from worker_exchange.delivery_handoff import validate_case


def main():
    folder = Path(__file__).resolve().parent
    repo = folder.parents[1]
    manifest = validate_execution(repo, folder.name)
    assignment = json.loads((repo / "inputs" / folder.name / "assignment.json").read_text())
    witness = json.loads((repo / "inputs" / folder.name / "witnesses.json").read_text())[0]["witness"]
    assignment["law"] = witness["law"]
    semantic = validate_semantic(folder, assignment, manifest)
    for entry in manifest["cases"]:
        validate_case(folder, entry, expected_sets=assignment["set_ids"])
    check_receipts(repo, folder, manifest)
    print(json.dumps({"cases": len(manifest["cases"]), "semantic": semantic,
                      "delivery_acceptance": "valid", "primary_compatibility": "valid"}, sort_keys=True))


if __name__ == "__main__":
    main()
