"""Validate the draft far-case contract against a source-bound CPU report."""
import argparse
import json
import sys
from pathlib import Path

FOLDER = Path(__file__).resolve().parent
REPO = FOLDER.parents[1]
sys.path.insert(0, str(REPO / 'runtime/scenario_pipeline'))
from worker_exchange.measurement_contract import validate, verify_report

CASE = 'testing__C109749__NRS-484B-253__motor_vehicle_driver__approaching_far'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--fixture', type=Path, required=True)
    args = parser.parse_args()
    fixture = args.fixture.resolve()
    contract = json.loads((FOLDER / 'cases/approaching_far/measurement-contract.json').read_text())
    finalizer = (FOLDER / 'cases/approaching_far/finalizer.py').read_text()
    plan = json.loads((FOLDER / 'case-plan.json').read_text())
    dispositions = plan['requirement_dispositions']
    # Prospective selection is validated in memory. The canonical plan stays
    # unchanged until the complete exact-case proof chain is available.
    for item in dispositions:
        if item['status'] == 'selected_required':
            item['case_ids'].append(CASE)
    rows = validate(contract, dispositions, finalizer, CASE)
    report = json.loads((fixture / 'analysis-report.json').read_text())
    verified = verify_report(contract, report, fixture)
    if set(verified) != {row['output_key'] for row in rows}:
        raise ValueError('Selected measurement keys differ from contract')
    if verified['far_approach_observation']['value']['legal_verdict_asserted']:
        raise ValueError('Draft observation cannot assert legal verdict')
    print(json.dumps({'format': 'far-measurement-contract-cpu-proof',
                      'case_id': CASE,
                      'selected_measurements': sorted(verified),
                      'source_hashes_verified': True,
                      'canonical_selection_modified': False,
                      'legal_verdict_asserted': False}, indent=2))


if __name__ == '__main__':
    main()
