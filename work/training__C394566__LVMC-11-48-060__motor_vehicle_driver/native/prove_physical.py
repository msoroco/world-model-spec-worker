"""Source-shaped route completion and lifecycle CPU fixtures, never CARLA evidence."""
import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EVENTS = ['capture_finished', 'encoders_closed', 'restoration_verified',
          'native_exit', 'owner_released', 'saved_processing_started']


def prove(probe, kind):
    if probe not in ('probe_01', 'probe_02'):
        raise ValueError('Unknown selected probe')
    manifest = json.loads((ROOT / 'execution-manifest.json').read_text())
    case = next(e for e in manifest['cases'] if e['case_id'].endswith('__' + probe))
    recipe = json.loads((ROOT / ('fixture-recipe-' + probe + '.json')).read_text())
    spec_path = ROOT / ('diagnostic-' + probe + '.json')
    if hashlib.sha256(spec_path.read_bytes()).hexdigest() != recipe['generator']['sha256']:
        raise ValueError('Source-shaped fixture recipe changed')
    spec = json.loads(spec_path.read_text())
    base = {'case_id': case['case_id'], 'construction_sha256': case['construction_sha256'],
            'provenance_kind': 'synthetic_fixture', 'diagnostic_fixture': True,
            'original_native_motion_verified': False, 'legal_verdict_claimed': False}
    if kind == 'lifecycle':
        return dict(base, events=EVENTS, exit_code=0)
    if kind not in ('complete_motion', 'incomplete_motion', 'missing_evidence'):
        raise ValueError('Unknown fixture kind')
    raw = spec['files']['native_route_trace.jsonl']
    rows = [json.loads(line) for line in raw.splitlines()]
    context = json.loads(spec['files']['route_context.json'])
    if len(rows) != 600 or context['case_id'] != case['case_id']:
        raise ValueError('Diagnostic case or route sample count changed')
    if kind == 'incomplete_motion':
        rows = [row for row in rows if row['road_id'] != context['exit_truck_route_id']]
    elif kind == 'missing_evidence':
        rows = []
    roads = []
    for row in rows:
        if not roads or roads[-1] != row['road_id']:
            roads.append(row['road_id'])
    joined = bool(rows) and all(row['video_frame'] == i for i, row in enumerate(rows))
    expected = [context['entry_truck_route_id'], context['intervening_street_id'],
                context['exit_truck_route_id']]
    complete = len(rows) == 600 and joined and roads == expected
    status = 'unverified' if not rows else 'met' if complete else 'not_met'
    return dict(base, physical_checks={'maneuver': {
        'status': status, 'method': 'source-shaped 600-frame road sequence and video-frame join',
        'sources': ['diagnostic-' + probe + '.json/native_route_trace.jsonl',
                    'diagnostic-' + probe + '.json/route_context.json'],
        'details': {'sample_count': len(rows), 'road_sequence': roads, 'joined': joined}}},
        maneuver_completed=complete,
        realized_observables=({'sample_count': len(rows), 'road_sequence': roads,
                               'joined': joined} if rows else {}),
        source_sha256={'native_route_trace.jsonl': hashlib.sha256(raw.encode()).hexdigest(),
                       'route_context.json': hashlib.sha256(spec['files']['route_context.json'].encode()).hexdigest()})


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--probe', required=True)
    parser.add_argument('--kind', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    result = prove(args.probe, args.kind)
    target = Path(args.output)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'case_id': result['case_id'], 'kind': args.kind,
                      'status': result.get('physical_checks', {}).get('maneuver', {}).get('status', 'lifecycle'),
                      'original_native_motion_verified': False}))


if __name__ == '__main__':
    main()
