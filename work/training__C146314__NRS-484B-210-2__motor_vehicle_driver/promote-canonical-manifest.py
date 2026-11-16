"""Promote the exact proof-bound CPU handoff after pinned validation."""
import json
import sys
from pathlib import Path

FOLDER = Path(__file__).resolve().parent
REPO = FOLDER.parents[1]
PREVIEW = FOLDER / 'execution-manifest-proof-bound-preview.json'
CANONICAL = FOLDER / 'execution-manifest.json'
sys.path[:0] = [str(REPO / 'runtime/pipeline'),
                str(REPO / 'runtime/pipeline/scenario_pipeline')]

from scenario_pipeline.worker_exchange.common import read
from scenario_pipeline.worker_exchange.delivery_handoff import validate_case
from scenario_pipeline.worker_exchange.execution_manifest import validate
from scenario_pipeline.worker_exchange.package_compatibility import check_receipts
from scenario_pipeline.worker_exchange.semantic_delivery import validate as validate_semantic


def main():
    manifest = read(PREVIEW)
    assert manifest['assignment_id'] == FOLDER.name
    assert len(manifest['cases']) == 2
    for entry in manifest['cases']:
        assert entry['delivery_acceptance']['original_native_observed'] is False
        assert read(FOLDER / entry['physical_preparation']['receipt'])['unit_mock'] is True
    manifest['status'] = 'delivery_prepared'
    CANONICAL.write_text(json.dumps(manifest, indent=2) + '\n')
    validated = validate(REPO, FOLDER.name)
    original = read(REPO / 'inputs' / FOLDER.name / 'assignment.json')
    validate_semantic(FOLDER, original, validated)
    for entry in validated['cases']:
        validate_case(FOLDER, entry, original.get('selection_targets'))
    check_receipts(REPO, FOLDER, validated)
    print(json.dumps({'assignment_id': FOLDER.name,
                      'cases': len(validated['cases']),
                      'candidates': sum(1 + len(e['candidates']) for e in validated['cases']),
                      'cpu_contracts_validated': True,
                      'original_native_observed': False,
                      'physical_acceptance_claimed': False}, sort_keys=True))


if __name__ == '__main__':
    main()
