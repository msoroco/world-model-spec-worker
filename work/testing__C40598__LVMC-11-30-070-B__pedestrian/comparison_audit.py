"""Independently audit fixed conditions and exact crossing contrasts."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from delivery_audit import audit, required, sha

ROOT = Path(__file__).resolve().parent
COMPARISONS = {
    'marked_vs_outside': ('marked', 'outside'),
    'unmarked_vs_outside': ('unmarked', 'outside'),
    'frontage_alternatives': ('outside', 'outside'),
}


def compare(comparison_id: str, first: Path, second: Path,
            diagnostic: bool = False) -> dict:
    plan = json.loads((ROOT / 'case-plan.json').read_text())
    declared = next((row for row in plan['comparisons']
        if row['comparison_id'] == comparison_id), None)
    if declared is None or comparison_id not in COMPARISONS:
        raise ValueError('unknown exact business-district comparison')
    attempts = [first.resolve(), second.resolve()]
    reports = []
    packets = []
    configs = []
    specs = []
    for attempt, case_id in zip(attempts, declared['case_ids']):
        reports.append(audit(attempt, case_id, diagnostic))
        packets.append(json.loads(required(attempt,
            'original-crossing-observations.json').read_text()))
        configs.append(json.loads(required(attempt, 'config.json').read_text()))
        specs.append(json.loads(required(attempt, 'case-spec.json').read_text()))
    if tuple(spec['crosswalk_category'] for spec in specs) != COMPARISONS[comparison_id]:
        raise ValueError('declared crosswalk contrast differs')
    left, right = packets
    for key in ('assignment_id', 'pedestrian_actor_id'):
        if left.get(key) != right.get(key):
            raise ValueError('fixed crossing identity differs: ' + key)
    for key in ('law_id', 'cell_id', 'actor', 'rate_hz', 'duration_s', 'cameras'):
        if configs[0].get(key) != configs[1].get(key):
            raise ValueError('fixed capture condition differs: ' + key)
    site_keys = ('roadway_id', 'roadway_polygon_xy_m', 'crosswalk_inventory',
                 'district_type', 'highway_span_ft', 'controls_source_sha256')
    for key in site_keys:
        if left['site'].get(key) != right['site'].get(key):
            raise ValueError('fixed roadway/crosswalk/control source differs: ' + key)
    if comparison_id == 'frontage_alternatives':
        if (specs[0]['district_frontage_review'] != 'frontage_alternative_1' or
                specs[1]['district_frontage_review'] != 'frontage_alternative_2' or
                left['site']['district_source_sha256'] == right['site']['district_source_sha256']):
            raise ValueError('reviewed frontage alternative contrast absent')
    elif (specs[0]['district_frontage_review'] != specs[1]['district_frontage_review'] or
          left['site']['district_source_sha256'] != right['site']['district_source_sha256']):
        raise ValueError('fixed business-district frontage source differs')
    if diagnostic:
        left_body = [frame['body_polygon_xy_m'] for frame in left['frames']]
        right_body = [frame['body_polygon_xy_m'] for frame in right['frames']]
        if comparison_id == 'frontage_alternatives' and left_body != right_body:
            raise ValueError('frontage comparison changed synthetic pedestrian route')
        if comparison_id != 'frontage_alternatives' and left_body == right_body:
            raise ValueError('crosswalk comparison did not change synthetic route')
    else:
        source_maps = [json.loads(required(attempt, 'reviewed-site.json').read_text())['sources']
                       for attempt in attempts]
        changed = {name for name in set(source_maps[0]) | set(source_maps[1])
                   if source_maps[0].get(name, {}).get('sha256') !=
                      source_maps[1].get(name, {}).get('sha256')}
        expected = {'district_frontage'} if comparison_id == 'frontage_alternatives' else {'pedestrian_route'}
        if changed != expected:
            raise ValueError('original source change differs from declared contrast: ' + str(sorted(changed)))
    if sha(attempts[0] / 'original-crossing-observations.json') == sha(
            attempts[1] / 'original-crossing-observations.json'):
        raise ValueError('comparison reused one original crossing source')
    return {'format': 'worker-comparison-audit', 'comparison_id': comparison_id,
        'case_ids': declared['case_ids'], 'passed': True, 'diagnostic_only': diagnostic,
        'physical_acceptance': False, 'legal_acceptance': False,
        'fixed_conditions': declared['fixed_conditions'],
        'deliberate_differences': declared['deliberate_differences'],
        'source_sha256': [sha(attempt / 'original-crossing-observations.json')
                          for attempt in attempts],
        'frame_counts': [report['frame_count'] for report in reports]}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--comparison', required=True)
    parser.add_argument('--first-attempt', type=Path, required=True)
    parser.add_argument('--second-attempt', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--diagnostic-fixture', action='store_true')
    args = parser.parse_args()
    for source in (args.first_attempt, args.second_attempt):
        if args.output.resolve() == source.resolve() or source.resolve() in args.output.resolve().parents:
            raise ValueError('comparison report must be outside original attempt')
    result = compare(args.comparison, args.first_attempt, args.second_attempt,
        args.diagnostic_fixture)
    if args.output.exists():
        raise ValueError('retain prior comparison report')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + '\n')
    print(json.dumps({'comparison_id': args.comparison, 'passed': True,
        'diagnostic_only': args.diagnostic_fixture}))


if __name__ == '__main__':
    main()
