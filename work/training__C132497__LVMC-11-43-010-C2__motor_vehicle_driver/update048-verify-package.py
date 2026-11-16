"""Read-only current-input verification of the selected roundabout CPU package."""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / 'runtime/pipeline'))
sys.path.insert(0, str(ROOT / 'runtime/pipeline/scenario_pipeline'))
from scenario_pipeline.worker_exchange.execution_manifest import validate as execution_validate  # noqa: E402
from scenario_pipeline.worker_exchange.semantic_delivery import validate as semantic_validate  # noqa: E402
from scenario_pipeline.worker_exchange.delivery_handoff import validate_case  # noqa: E402
from scenario_pipeline.worker_exchange.package_compatibility import check_receipts  # noqa: E402


def main():
    manifest = execution_validate(ROOT, HERE.name)
    assignment = json.loads((ROOT / 'inputs' / HERE.name / 'assignment.json').read_text())
    semantic = semantic_validate(HERE, assignment, manifest)
    for entry in manifest['cases']:
        validate_case(HERE, entry, assignment['selection_targets'])
    check_receipts(ROOT, HERE, manifest)
    candidates = json.loads((HERE / 'update048-proof-matrix.json').read_text())
    pairs = json.loads((HERE / 'update048-pair-audit.json').read_text())
    if (candidates.get('passed') is not True or candidates.get('candidate_count') != 8 or
            pairs.get('passed') is not True or pairs.get('pair_count') != 4):
        raise ValueError('Current-input candidate or pair audit incomplete')
    print(json.dumps({'cases': len(manifest['cases']), 'semantic_stages': semantic['stage_count'],
                      'delivery_contracts': len(manifest['cases']), 'candidate_chains': 8,
                      'pair_audits': 4, 'passed': True,
                      'scope': 'CPU preparation; original Native and legal outcome unverified'}))


if __name__ == '__main__':
    main()
