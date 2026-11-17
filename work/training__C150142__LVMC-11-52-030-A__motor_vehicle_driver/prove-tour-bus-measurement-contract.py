"""Check a text-4 draft contract against an actual saved-analysis report.

The in-memory text-4 selection leaves the authored case plan unchanged. This
is a source-bound diagnostic receipt, not a selected delivery receipt.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
sys.path.insert(0, str(REPO / 'runtime/pipeline/scenario_pipeline'))
from worker_exchange.measurement_contract import validate, verify_report


def prove(suffix, stage):
    if suffix not in tuple(service + '_' + boundary
                           for service in ('tour_bus', 'shuttle_bus', 'rtc_bus', 'limo')
                           for boundary in ('below', 'at', 'above', 'no_loading')):
        raise ValueError('Unsupported signed-bus case')
    stage = Path(stage).resolve()
    if REPO / '.runtime-work' not in stage.parents:
        raise ValueError('Saved-analysis stage belongs under .runtime-work')
    if (stage / 'analysis').is_dir():
        stage = stage / 'analysis'
    case_id = ROOT.name + '__' + suffix
    plan = json.loads((ROOT / 'case-plan.json').read_text())
    dispositions = [dict(row) for row in plan['requirement_dispositions']]
    requirement = 'text-5' if suffix.startswith('rtc_bus_') else 'text-4'
    for row in dispositions:
        row['status'] = ('selected_required' if row['requirement'] == requirement
                         else 'exception_pending')
    contract_path = (ROOT / 'selected-primary' / suffix /
                     'selected-measurement-contracts' / (suffix + '.json'))
    contract = json.loads(contract_path.read_text())
    validate(contract, dispositions, (stage / 'finalize_selected.py').read_text(),
             case_id)
    report_path = stage / 'analysis-report.json'
    values = verify_report(contract, json.loads(report_path.read_text()), stage)
    observed = values['signed_curb_observation']['value']
    return {'case_id': case_id, 'actual_case_plan_changed': False,
            'contract_valid_under_in_memory_' + requirement.replace('-', '') + '_selection': True,
            'report_sha256': hashlib.sha256(report_path.read_bytes()).hexdigest(),
            'contract_sha256': hashlib.sha256(contract_path.read_bytes()).hexdigest(),
            'source_bound_measurements': ['signed_curb_observation'],
            'reported_duration_s': observed['red_curb_stationary_duration_s'],
            'reported_boundary': observed['duration_relative_to_30_minutes'],
            'reported_activity_events': len(observed['recorded_activity_events']),
            'legal_verdict': observed['legal_verdict'],
            'original_native_observed': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True)
    parser.add_argument('--stage', required=True)
    args = parser.parse_args()
    print(json.dumps(prove(args.case, args.stage), sort_keys=True))
