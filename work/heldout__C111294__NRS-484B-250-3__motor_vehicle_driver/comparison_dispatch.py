"""Run an exact independent comparison against retained saved attempts."""

import argparse
import json
from pathlib import Path

from arrival_timing_audit import audit as audit_arrival
from ending_road_comparison_audit import audit as audit_order
from highway_continuity_comparison_audit import audit_attempts as audit_continuity
from official_control_comparison_audit import audit_attempts as audit_control
from official_phase_comparison_audit import audit as audit_phase
from yield_release_sweep_audit import audit as audit_release


HERE = Path(__file__).resolve().parent


def dispatch(comparison_id, attempts, analysis_roots=()):
    plan = json.loads((HERE / 'case-plan.json').read_text())
    selected = [row for row in plan['comparisons']
                if row['comparison_id'] == comparison_id]
    if len(selected) != 1:
        raise ValueError('Unknown or duplicate exact comparison: ' + comparison_id)
    expected = selected[0]['case_ids']
    if len(attempts) != len(expected):
        raise ValueError('Exact comparison attempt count differs')
    if analysis_roots and len(analysis_roots) != len(expected):
        raise ValueError('Exact comparison analysis count differs')
    roots = [Path(root) for root in attempts]
    for root, case_id in zip(roots, expected):
        config = json.loads((root / 'config.json').read_text())
        if config.get('selected_case_id') != case_id:
            raise ValueError('Exact comparison attempt selects another case: ' + case_id)
    if comparison_id == 'ending_through_yield_order':
        result = audit_order(*roots)
    elif comparison_id == 'arrival_timing_applicability':
        result = audit_arrival(*roots)
    elif comparison_id == 'official_control_exception':
        result = audit_control(*roots)
    elif comparison_id == 'yield_release_delay_sweep':
        if not analysis_roots:
            raise ValueError('Release sweep needs saved analysis roots')
        result = audit_release(roots, analysis_roots)
    elif comparison_id == 'official_device_red_green':
        result = audit_phase(*roots)
    elif comparison_id == 'ending_vs_continuing_highway':
        result = audit_continuity(*roots)
    else:
        raise ValueError('No exact independent audit for ' + comparison_id)
    if result.get('comparison_id') != comparison_id:
        raise ValueError('Independent audit returned another comparison')
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--comparison', required=True)
    parser.add_argument('--attempt', action='append', required=True)
    parser.add_argument('--analysis-root', action='append')
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    result = dispatch(args.comparison, args.attempt, args.analysis_root or ())
    Path(args.output).write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'comparison_id': result['comparison_id'],
                      'physical_or_legal_acceptance_claimed': False}))


if __name__ == '__main__':
    main()
