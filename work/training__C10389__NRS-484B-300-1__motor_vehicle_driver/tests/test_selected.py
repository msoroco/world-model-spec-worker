"""Integrated CPU proof of the source-bound selected device proposal."""
import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
ROOT = HERE.parents[1].resolve()
OUTPUT = Path(os.environ.get('SCENARIO_PIPELINE_OUTPUT_ROOT', '')).resolve()
if ROOT / '.runtime-work' not in OUTPUT.parents:
    raise RuntimeError('Runtime output must be under .runtime-work')
sys.path[:0] = [str(ROOT / 'runtime'), str(ROOT / 'runtime/scenario_pipeline')]

from scenario_pipeline.worker_exchange.execution_manifest import validate as execution
from scenario_pipeline.worker_exchange.semantic_delivery import validate as semantic
from scenario_pipeline.worker_exchange.package_compatibility import check_receipts
from scenario_pipeline.worker_exchange.delivery_handoff import validate_case


def read(path):
    return json.loads(path.read_text())


def main():
    aid = HERE.name
    manifest = execution(ROOT, aid)
    assignment = read(ROOT / 'inputs' / aid / 'assignment.json')
    stages = semantic(HERE, assignment, manifest)
    assert stages['selected_cases'] == 12 and stages['stage_count'] == 8
    assert check_receipts(ROOT, HERE, manifest)
    for entry in manifest['cases']:
        assert validate_case(HERE, entry, assignment['selection_targets'])['case_id'] == entry['case_id']
        probe = entry['case_id'].rsplit('__', 1)[1]
        receipt = read(HERE / 'physical-proof' / probe / 'proof.json')
        assert receipt['original_native_observed'] is False
        assert {f['kind'] for f in receipt['fixtures']} == {
            'complete_motion', 'incomplete_motion', 'missing_evidence'}
        diagnostic_path = (HERE / 'delivery-proofs' / probe / 'diagnostic.json') if probe.startswith('probe_') else (HERE / 'delivery-proof' / probe / 'primary-diagnostic.json')
        diagnostic = read(diagnostic_path)
        assert diagnostic['accepted'] is False and diagnostic['diagnostic_only'] is True
    comparison = read(HERE / 'comparison-proof/diagnostic.json')
    assert comparison['accepted'] is False and len(comparison['case_ids']) == 2
    branch_comparison = read(HERE / 'cases/branch-requests/branch-comparison-proof.json')
    assert len(branch_comparison['comparisons']) == 3
    applicability = read(HERE / 'cases/branch-requests/signal-law-applicability.json')
    assert applicability['authored_source']['junction_count'] == 0
    assert 'not established' in applicability['disposition']
    placement = read(HERE / 'cases/branch-requests/placement-pair-proof.json')
    assert placement['official_placement_verified'] is False
    print(json.dumps({'assignment_id': aid, 'selected_cases': 12,
                      'candidate_constructions': 26, 'semantic_stages': 8,
                      'package_receipts_validated': True,
                      'independent_delivery_contracts': 12,
                      'physical_synthetic_fixture_suites': 12,
                      'comparison_diagnostic': True,
                      'original_native_observed': False,
                      'delivery_ready_claimed': False}))


if __name__ == '__main__':
    main()
