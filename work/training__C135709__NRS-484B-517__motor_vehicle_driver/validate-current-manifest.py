"""Run pinned static validators for the current exact C135709 CPU manifest."""
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
sys.path.insert(0, str(REPO/'runtime/pipeline'))
sys.path.insert(0, str(REPO/'runtime/pipeline/scenario_pipeline'))
from scenario_pipeline.worker_exchange.execution_manifest import validate
from scenario_pipeline.worker_exchange.semantic_delivery import validate as semantic
from scenario_pipeline.worker_exchange.delivery_handoff import validate_case
from scenario_pipeline.worker_exchange.package_compatibility import check_receipts


def main():
    manifest = validate(REPO, ROOT.name)
    original = json.loads((REPO/'inputs'/ROOT.name/'assignment.json').read_text())
    stages = semantic(ROOT, original, manifest)
    for entry in manifest['cases']:
        validate_case(ROOT, entry, original['selection_targets'])
    check_receipts(REPO, ROOT, manifest)
    print(json.dumps({'exact_cases': len(manifest['cases']),
                      'semantic_stages': stages['stage_count'],
                      'delivery_contracts': len(manifest['cases']),
                      'primary_compatibility_receipts': len(manifest['cases']),
                      'delivery_ready': False}))


if __name__ == '__main__':
    main()
