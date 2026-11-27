"""Independent paired audit of original lane use with fixed roundabout context."""
import argparse
import hashlib
import json
from pathlib import Path

from delivery_audit import audit as audit_delivery
from finalize import analyze

HERE = Path(__file__).resolve().parent


def require(condition, message):
    if not condition:
        raise ValueError(message)


def pairs(values):
    output = {}
    for value in values:
        case, separator, path = value.partition('=')
        if not separator or not case or not path or case in output:
            raise ValueError('Each case path needs unique CASE=PATH form')
        output[case] = Path(path).resolve()
    return output


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def compare(comparison_id, attempts, processing, diagnostic=False, missing_source=None,
            diagnostic_geometry_change=False):
    plan = json.loads((HERE / 'case-plan.json').read_text())
    matches = [item for item in plan['comparisons'] if item['comparison_id'] == comparison_id]
    require(len(matches) == 1, 'Unknown exact statutory comparison')
    members = matches[0]['case_ids']
    require(len(members) == 2 and set(attempts) == set(members) and set(processing) == set(members),
            'Comparison lacks exact member attempts or processing receipts')
    records = {}
    for case in members:
        attempt = attempts[case]
        audit_delivery(case, attempt, processing[case], diagnostic, missing_source)
        config = json.loads((attempt / 'config.json').read_text())
        measurement = analyze(attempt)['measurement']
        controls = [json.loads(line) for line in (attempt / 'control-intent.jsonl').read_text().splitlines()]
        actors = [json.loads(line) for line in (attempt / 'native-raw-actors.jsonl').read_text().splitlines()]
        records[case] = {'config': config, 'measurement': measurement,
                         'road_sha256': sha(attempt / 'road.xodr'),
                         'map_sha256': sha(attempt / 'roundabout-map-readback.json'),
                         'intent': {row['exit_intent'] for row in controls},
                         'lane_ids': {row['actors'][0]['lane_id'] for row in actors
                                      if row['actors'][0]['road_id'] in (1, 2, 3, 4)}}
    a, b = (records[case] for case in members)
    if diagnostic_geometry_change:
        require(diagnostic, 'Synthetic geometry mutation requires diagnostic mode')
        b['road_sha256'] = 'diagnostic-changed-road-source'
    require(a['road_sha256'] == b['road_sha256'] and a['map_sha256'] == b['map_sha256'],
            'Undeclared roundabout geometry or topology difference')
    for key in ('rate_hz', 'duration_s', 'frames', 'cameras', 'actor', 'cell_id',
                'required_atoms', 'source_packets', 'steer_gain'):
        require(a['config'].get(key) == b['config'].get(key),
                'Undeclared fixed capture/controller difference: ' + key)
    require(len(a['intent']) == len(b['intent']) == 1 and a['intent'] == b['intent'],
            'Exit intention differs within lane-choice comparison')
    expected = 'u_turn' if 'u_turn' in comparison_id else 'left_turn'
    require(a['intent'] == {expected}, 'Wrong statutory exit alternative')
    require(a['lane_ids'] == {-1} and b['lane_ids'] == {-2},
            'Lane-choice comparison lacks distinct original ring lane readback')
    ma, mb = a['measurement'], b['measurement']
    require(ma['left_lane_frame_count'] > 0 and ma['right_lane_frame_count'] == 0
            and mb['right_lane_frame_count'] > 0 and mb['left_lane_frame_count'] == 0,
            'Lane-choice comparison lacks distinct sourced occupancy')
    require(ma['exit_intent'] == mb['exit_intent'] == expected,
            'Sourced exit alternative differs')
    return {'comparison_id': comparison_id, 'case_ids': members, 'diagnostic_only': diagnostic,
            'fixed_geometry_capture_intent_checked': True,
            'source_bound_lane_occupancy': {case: records[case]['measurement']
                                             for case in members},
            'legal_verdict': None, 'physical_acceptance_claimed': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--comparison', required=True)
    parser.add_argument('--attempt', action='append', default=[], metavar='CASE=PATH')
    parser.add_argument('--processing', action='append', default=[], metavar='CASE=PATH')
    parser.add_argument('--diagnostic', action='store_true')
    parser.add_argument('--missing-source')
    parser.add_argument('--diagnostic-geometry-change', action='store_true')
    args = parser.parse_args()
    print(json.dumps(compare(args.comparison, pairs(args.attempt), pairs(args.processing),
                             args.diagnostic, args.missing_source,
                             args.diagnostic_geometry_change), sort_keys=True))
