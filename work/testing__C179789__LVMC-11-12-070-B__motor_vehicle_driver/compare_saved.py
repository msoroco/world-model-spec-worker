"""Compare independently audited original through-highway attempts."""
import argparse
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def require(ok, message):
    if not ok:
        raise ValueError(message)


def compare(index, expected_comparison_id):
    plan = json.loads((HERE / 'case-plan.json').read_text())
    matches = [row for row in plan['comparisons'] if row['comparison_id'] == expected_comparison_id]
    require(len(matches) == 1, 'expected comparison identity missing')
    row = matches[0]
    reports = []
    for case_id in row['case_ids']:
        path = Path(index.get(case_id, ''))
        require(path.is_file() and not path.is_symlink(), 'original comparison audit missing: ' + case_id)
        report = json.loads(path.read_text())
        require(report.get('format') == 'c179789-original-delivery-audit-v1'
                and report.get('case_id') == case_id and report.get('frame_count') == 900
                and report.get('physical_completion') is True
                and report.get('antecedent_legal_review') == 'unresolved'
                and report.get('right_of_way_legal_review') == 'unresolved',
                'comparison member lacks original independent audit')
        reports.append(report)
    first = reports[0]
    for report in reports[1:]:
        for key in ('map_sha256', 'intersection_id', 'entering_maneuver', 'fixed_sources'):
            require(report.get(key) == first.get(key), 'fixed original comparison source changed: ' + key)
    if expected_comparison_id.startswith('engineering_antecedent_pause'):
        require(len(reports) == 3, 'antecedent grid needs three original cases')
        request = [report['engineering_request']['antecedent_pause_s'] for report in reports]
        measured = [report['through_highway_measurement']['entering_preentry_pause_s'] for report in reports]
        require(len(set(request)) == len(set(measured)) == 3, 'antecedent engineering grid collapsed')
        difference = 'entering_preentry_pause_s'
    elif expected_comparison_id.startswith('engineering_precedence_speed'):
        require(len(reports) == 3, 'precedence grid needs three original cases')
        request = [report['engineering_request']['through_approach_speed_mps'] for report in reports]
        measured = [report['through_highway_measurement']['through_preentry_min_speed_mps'] for report in reports]
        require(len(set(request)) == len(set(measured)) == 3, 'precedence engineering grid collapsed')
        difference = 'through_preentry_min_speed_mps'
    else:
        require(len(reports) == 2 and reports[0]['through_request'] == 'yield_request'
                and reports[1]['through_request'] == 'continue_request',
                'through-driver response comparison changed')
        request = [report['through_request'] for report in reports]
        measured = [report['through_highway_measurement']['through_preentry_min_speed_mps'] for report in reports]
        difference = 'through_request'
    return {'format': 'c179789-original-comparison-audit-v1',
            'comparison_id': expected_comparison_id, 'case_ids': row['case_ids'],
            'declared_difference': difference, 'requested_values': request,
            'measured_values': measured, 'legal_status': 'unresolved',
            'source_kind': 'original_native_capture'}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--index', type=Path, required=True)
    parser.add_argument('--expected-comparison-id', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError('retain prior original comparison audit')
    args.output.write_text(json.dumps(compare(json.loads(args.index.read_text()),
                                              args.expected_comparison_id), indent=2) + '\n')


if __name__ == '__main__':
    main()
