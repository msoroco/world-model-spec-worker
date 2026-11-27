"""Independent controlled comparison of exact service parking delivery reviews."""

import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
VARIABLE = {'vehicle_status': 'city_vehicle',
            'council_designation': 'council_designated',
            'official_posting': 'official_posting',
            'governed_space_occupancy': 'all_footprints_overlap_governed_space'}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def audit(comparison_id, report_dir, *, synthetic_fixture=False):
    plan = json.loads((ROOT / 'case-plan.json').read_text())
    comparison = next((row for row in plan['comparisons']
                       if row['comparison_id'] == comparison_id), None)
    if comparison is None or comparison_id not in VARIABLE:
        raise ValueError('unknown exact service parking comparison')
    report_dir = Path(report_dir)
    reports = []
    for case_id in comparison['case_ids']:
        path = report_dir / (case_id.rsplit('__', 1)[-1] + '.json')
        report = json.loads(path.read_text())
        expected_scope = ('synthetic CPU audit proof only' if synthetic_fixture
                          else 'original Native delivery review')
        if (report.get('format') != 'worker-delivery-audit' or
                report.get('passed') is not True or report.get('case_id') != case_id or
                report.get('scope') != expected_scope or
                report.get('physical_completion_reviewed') is not True or
                report.get('legal_verdict_claimed') is not False):
            raise ValueError('source-bound exact delivery audit missing: ' + case_id)
        reports.append((path, report))
    fixed = ('cell_id', 'actor', 'camera_contract_sha256', 'duration_s',
             'candidate_id', 'city_location_kind', 'governed_space_rect_m')
    first, second = reports[0][1], reports[1][1]
    if any(first.get(key) != second.get(key) for key in fixed):
        raise ValueError('controlled service parking comparison changed fixed conditions')
    variable = VARIABLE[comparison_id]
    state_a, state_b = first['measured'], second['measured']
    compared = ('city_vehicle', 'council_designated', 'official_posting',
                'all_footprints_overlap_governed_space')
    if state_a.get(variable) == state_b.get(variable):
        raise ValueError('deliberate service parking condition did not vary')
    if any(state_a.get(name) != state_b.get(name) for name in compared if name != variable):
        raise ValueError('more than one service parking condition varied')
    if state_a.get('parked_frames') != state_b.get('parked_frames'):
        raise ValueError('parked interval changed across controlled comparison')
    return {'format': 'worker-comparison-audit', 'passed': True,
            'comparison_id': comparison_id, 'case_ids': comparison['case_ids'],
            'reports_sha256': {path.name: sha(path) for path, _ in reports},
            'fixed_conditions_checked': list(fixed),
            'deliberate_differences': comparison['deliberate_differences'],
            'varied_condition': variable,
            'scope': 'synthetic CPU comparison proof only' if synthetic_fixture else 'original Native delivery review',
            'legal_verdict_claimed': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--comparison', required=True)
    parser.add_argument('--report-dir', required=True)
    args = parser.parse_args()
    print(json.dumps(audit(args.comparison, args.report_dir), indent=2))
