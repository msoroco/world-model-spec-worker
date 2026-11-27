"""Independent original-only entrance distance, side and exception pairs."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from fire_station_scene import ASSIGNMENT, case_by_id


ROOT = Path(__file__).resolve().parent
PLAN = json.loads((ROOT / 'case-plan.json').read_text(encoding='utf-8'))
PAIRS = {pair['comparison_id']: pair['case_ids'] for pair in PLAN['comparisons']}


def require(ok, message):
    if not ok:
        raise ValueError(message)


def audit_pair(comparison_id, reports):
    ids = PAIRS.get(comparison_id)
    require(ids is not None and len(ids) == 2, 'unknown fire-station comparison')
    pair = [reports.get(case_id) for case_id in ids]
    for case_id, report in zip(ids, pair):
        require(isinstance(report, dict) and
                report.get('format') == 'worker-delivery-audit' and
                report.get('passed') is True and
                report.get('protocol_fixture_checked') is False and
                report.get('case_id') == case_id and
                report.get('frame_count') == 900 and
                report.get('physical_acceptance_claimed') is True and
                report.get('comparison_record', {}).get('source_kind') ==
                'original_native_capture',
                'original accepted report required: ' + case_id)
    a, b = [report['comparison_record'] for report in pair]
    left, right = [case_by_id(case_id) for case_id in ids]
    require(left is not None and right is not None,
            'comparison case identity absent')
    for record, case in ((a, left), (b, right)):
        require((record.get('side_request'), record.get('activity_request'),
                 record.get('distance_request_ft'),
                 record.get('circumstance_request')) ==
                (case.side, case.activity, case.distance_ft, case.circumstance),
                'original case variables differ')
        expected_fire = case.circumstance != 'non_fire_station'
        expected_public = case.circumstance != 'private_road'
        require(record.get('station_is_fire') is expected_fire and
                record.get('highway_public_use') is expected_public,
                'original fire-station or highway negative control differs')
        measure = record.get('measurement', {})
        require(measure.get('case_id') == case.case_id and
                len(measure.get('observations', [])) == 900 and
                isinstance(measure.get('minimum_observed_vertex_to_entrance_m'),
                           (int, float)),
                'original body/entrance measurements absent')
    require(a.get('camera_plan') and a['camera_plan'] == b.get('camera_plan') and
            a.get('duration_s') == b.get('duration_s') == 45,
            'changed fixed camera or duration condition')
    first_sources, second_sources = a.get('source_sha256', {}), b.get('source_sha256', {})
    require(first_sources and second_sources, 'source-hashed original site missing')
    changed = {name for name in set(first_sources) | set(second_sources)
               if first_sources.get(name) != second_sources.get(name)}
    deliberate = {key for key in ('side', 'activity', 'distance_ft', 'circumstance')
                  if getattr(left, key) != getattr(right, key)}
    require(len(deliberate) == 1, 'comparison changes multiple case variables')
    variable = next(iter(deliberate))
    allowed_source_changes = {
        'side': set(), 'distance_ft': set(), 'activity': {'person'},
        'circumstance': {'authority', 'station', 'highway'}}[variable]
    require(changed <= allowed_source_changes,
            'changed fixed original condition: ' + ','.join(sorted(changed - allowed_source_changes)))
    if variable == 'circumstance':
        if right.circumstance == 'non_fire_station':
            require('station' in changed, 'fire-station source did not change')
        if right.circumstance == 'private_road':
            require('highway' in changed, 'highway public-use source did not change')
    x = a['measurement']['minimum_observed_vertex_to_entrance_m']
    y = b['measurement']['minimum_observed_vertex_to_entrance_m']
    if variable == 'distance_ft':
        require((y-x)*(right.distance_ft-left.distance_ft) > 0,
                'original vehicle/entrance distance contrast absent')
    if variable == 'side':
        def observed_side(measure):
            entrance = measure['entrance_lateral_m']
            samples = measure['observations']
            opposite = all(row['vehicle_lateral_max_m'] * entrance < 0 and
                           row['vehicle_lateral_min_m'] * entrance < 0
                           for row in samples)
            same = all(row['vehicle_lateral_max_m'] * entrance > 0 and
                       row['vehicle_lateral_min_m'] * entrance > 0
                       for row in samples)
            return 'opposite' if opposite else 'entrance' if same else 'ambiguous'
        require(observed_side(a['measurement']) == left.side and
                observed_side(b['measurement']) == right.side,
                'original highway-side contrast absent')
    return {
        'format': 'c229925-independent-original-comparison-v1',
        'comparison_id': comparison_id, 'case_ids': ids,
        'deliberate_variable': variable,
        'fixed_source_sha256': {name: digest for name, digest in first_sources.items()
                                if name not in allowed_source_changes},
        'sampled_minimum_vertex_distances_m': [x, y],
        'physical_comparison_passed': True,
        'legal_verdict_claimed': False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--comparison', choices=tuple(PAIRS), required=True)
    parser.add_argument('--left-report', type=Path, required=True)
    parser.add_argument('--right-report', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    ids = PAIRS[args.comparison]
    reports = {ids[0]: json.loads(args.left_report.read_text()),
               ids[1]: json.loads(args.right_report.read_text())}
    result = audit_pair(args.comparison, reports)
    if args.output.exists():
        raise ValueError('refusing to overwrite prior comparison audit')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(result))


if __name__ == '__main__':
    main()
