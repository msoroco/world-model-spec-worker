"""Independent original-only excavation placement, passage and exception comparisons."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from excavation_park import CASES

AID = 'testing__C229405__NRS-484B-450-1k__motor_vehicle_driver'
PAIRS = {
    'alongside_vs_opposite': ('alongside_park_narrow', 'opposite_park_narrow'),
    'narrow_vs_open_passage': ('alongside_park_narrow', 'alongside_park_open'),
    'park_vs_conflict_stop': ('alongside_park_narrow', 'alongside_stop_conflict'),
    'park_vs_officer_stand': ('alongside_park_narrow', 'alongside_stand_officer'),
    'park_vs_device': ('alongside_park_narrow', 'alongside_park_device'),
    'park_vs_law': ('alongside_park_narrow', 'alongside_park_law'),
    'park_vs_ordinary_stop': ('alongside_park_narrow', 'alongside_stop_ordinary'),
    'park_vs_ordinary_stand': ('alongside_park_narrow', 'alongside_stand_ordinary'),
    'ordinary_stop_vs_conflict_stop': ('alongside_stop_ordinary', 'alongside_stop_conflict'),
    'ordinary_stand_vs_officer_stand': ('alongside_stand_ordinary', 'alongside_stand_officer'),
}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def audit_pair(comparison_id, reports):
    suffixes = PAIRS.get(comparison_id)
    require(suffixes is not None, 'unknown excavation comparison')
    ids = [AID + '__' + suffix for suffix in suffixes]
    pair = [reports.get(case_id) for case_id in ids]
    for case_id, report in zip(ids, pair):
        require(isinstance(report, dict) and report.get('format') == 'worker-delivery-audit' and
                report.get('passed') is True and report.get('protocol_fixture_checked') is False and
                report.get('case_id') == case_id and report.get('frame_count') == 900 and
                report.get('physical_acceptance_claimed') is True and
                report.get('comparison_record', {}).get('source_kind') == 'original_native_capture',
                'original accepted report required: ' + case_id)
    a, b = [report['comparison_record'] for report in pair]
    for key in ('fixed_source_sha256', 'camera_plan', 'duration_s'):
        require(a.get(key) and a[key] == b.get(key), 'changed fixed original condition: ' + key)
    left, right = [next(case for case in CASES if case.case_id == suffix) for suffix in suffixes]
    for record, case in ((a, left), (b, right)):
        require((record.get('requested_relation'), record.get('activity'),
                 record.get('passage_probe'), record.get('exception')) ==
                (case.relation, case.activity, case.passage, case.exception),
                'original case variables differ')
    x, y = a['measurement'], b['measurement']
    require(x.get('frame_count') == y.get('frame_count') == 900,
            'original measurement frame count differs')
    widths = [x.get('minimum_available_passage_width_m'),
              y.get('minimum_available_passage_width_m')]
    gaps = [x.get('minimum_body_excavation_gap_m'),
            y.get('minimum_body_excavation_gap_m')]
    require(all(type(v) in (int, float) and v >= 0 for v in widths + gaps),
            'original passage/body measurement absent')
    if comparison_id == 'narrow_vs_open_passage':
        require(widths[0] < widths[1], 'original open/narrow passage contrast absent')
    elif comparison_id == 'alongside_vs_opposite':
        require(left.relation != right.relation, 'original relation contrast absent')
    else:
        require(left.relation == right.relation == 'alongside', 'relation changed')
        require(left.passage == right.passage == 'narrow', 'passage probe changed')
        if comparison_id in ('park_vs_ordinary_stop', 'park_vs_ordinary_stand'):
            require(left.exception == right.exception == 'none' and left.activity != right.activity,
                    'isolated ordinary halt activity contrast absent')
        if comparison_id in ('ordinary_stop_vs_conflict_stop',
                             'ordinary_stand_vs_officer_stand'):
            require(left.activity == right.activity and left.exception != right.exception,
                    'isolated exception context contrast absent')
    return {'format': 'c229405-independent-original-comparison-v1',
            'comparison_id': comparison_id, 'case_ids': ids,
            'fixed_source_sha256': a['fixed_source_sha256'],
            'minimum_available_passage_widths_m': widths,
            'minimum_body_excavation_gaps_m': gaps,
            'physical_comparison_passed': True, 'legal_verdict_claimed': False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--report-map', type=Path, required=True)
    parser.add_argument('--comparison', choices=tuple(PAIRS), required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    paths = json.loads(args.report_map.read_text())
    reports = {case_id: json.loads(Path(path).read_text()) for case_id, path in paths.items()}
    result = audit_pair(args.comparison, reports)
    if args.output.exists():
        raise ValueError('refusing to overwrite prior comparison audit')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result))


if __name__ == '__main__':
    main()
