"""CPU-only source-joined physical outcome and lifecycle fixture protocol.

The complete fixture is synthetic Native-shaped motion, not an actual capture,
pavement finding, immediate hazard, or legal act.
"""

import argparse
from hashlib import sha256
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
EVENTS = ['capture_finished', 'encoders_closed', 'restoration_verified',
          'native_exit', 'owner_released', 'saved_processing_started']


def digest(path):
    return sha256(Path(path).read_bytes()).hexdigest()


def rows(text):
    return [json.loads(line) for line in text.splitlines() if line.strip()]


def observed_passes(passing):
    count = 0
    for phase in ('first_right_pass_request', 'second_right_pass_request'):
        segment = [x for x in passing if x['requested_phase'] == phase]
        if len(segment) < 2:
            continue
        before = segment[0]['ego_station_m'] - segment[0]['lead_station_m']
        after = segment[-1]['ego_station_m'] - segment[-1]['lead_station_m']
        if before < -5 and after > 5 and any(x['right_of_mapped_road_edge_m'] > 0
                                             for x in segment):
            count += 1
    return count


def evaluate(case, kind):
    manifest = json.loads((HERE / 'execution-manifest.json').read_text())
    entry = next((x for x in manifest['cases'] if x['case_id'] == case), None)
    if entry is None or kind not in ('complete_motion', 'incomplete_motion', 'missing_evidence'):
        raise ValueError('Unknown exact case or physical fixture kind')
    construction = HERE / entry['construction']
    if digest(construction) != entry['construction_sha256']:
        raise ValueError('Exact physical construction changed')
    recipe = json.loads((ROOT / entry['fixture_recipe']).read_text())
    source = ROOT / recipe['sources'][0]['source']
    if digest(source) != recipe['sources'][0]['sha256']:
        raise ValueError('Original-shaped diagnostic source changed')
    diagnostic = json.loads(source.read_text())
    files = diagnostic['files']
    frame_map = rows(files['video_frames.jsonl'])
    motion = rows(files['driving_trace.jsonl'])
    following = rows(files['following_sources.jsonl'])
    passing = rows(files['right_pass_sources.jsonl'])
    if len(frame_map) < 3 or not (len(frame_map) == len(motion) == len(following) == len(passing)):
        raise ValueError('Original-shaped four-source frame coverage differs')
    actor_ids = set()
    for i, (frame, ego, bodies, road) in enumerate(zip(frame_map, motion, following, passing)):
        identity = (frame['carla_frame'], frame['time_s'])
        if (frame['video_frame'] != i or any((x['frame'], x['time_s']) != identity
                                            for x in (ego, bodies, road))):
            raise ValueError('Original-shaped frame/time join differs')
        actor_ids.add((road['ego_actor_id'], road['fixed_overtaken_actor_id']))
        if (road['ego_actor_id'], road['fixed_overtaken_actor_id']) != (
                bodies['ego']['actor_id'], bodies['lead']['actor_id']):
            raise ValueError('Fixed overtaken actor source differs')
    if len(actor_ids) != 1:
        raise ValueError('Overtaken actor changes across the continuous drive')
    if {x['path'] for x in diagnostic['videos']} != {
            'overview.mkv', 'approach.mkv', 'reference_corner.mkv', 'driver_reference.mkv'}:
        raise ValueError('Four source-camera fixture specification missing')
    expected = 1 if case.endswith('__single_right_pass') else 2
    if kind == 'missing_evidence':
        passing = None
    elif kind == 'incomplete_motion':
        passing = [dict(x) for x in passing]
        for x in passing:
            if x['requested_phase'] == 'first_right_pass_request':
                x['right_of_mapped_road_edge_m'] = -1
    measured = observed_passes(passing) if passing is not None else None
    status = ('unverified' if measured is None else
              'met' if measured == expected else 'not_met')
    if status != {'complete_motion': 'met', 'incomplete_motion': 'not_met',
                  'missing_evidence': 'unverified'}[kind]:
        raise ValueError('Two-pass physical fixture classification differs')
    return {'format': 'worker-physical-fixture-outcome', 'case_id': case,
            'fixture_kind': kind, 'fixture_only': True, 'diagnostic_fixture': True,
            'actual_native_capture': False,
            'physical_checks': {'maneuver': {'status': status,
                'method': 'original-shaped fixed-actor, frame-joined mapped-edge and route order-reversal classifier; no pavement or legal finding',
                'sources': {'construction': entry['construction'],
                    'construction_sha256': entry['construction_sha256'],
                    'diagnostic': recipe['sources'][0]['source'],
                    'diagnostic_sha256': digest(source),
                    'frame_count': len(frame_map), 'expected_passes': expected,
                    'measured_passes': measured},
                'missing_evidence': ['right_pass_sources.jsonl'] if passing is None else []}},
            'maneuver_completed': status == 'met',
            'realized_observables': {'synthetic_mapped_edge_passes': measured,
                                     'synthetic_frames': len(frame_map)} if status == 'met' else {},
            'provenance_kind': 'native',
            'provenance_note': 'Native-shaped synthetic protocol only; no CARLA or legal completion',
            'physical_acceptance_claimed': False, 'legal_acceptance_claimed': False}


def lifecycle(out_of_order=False):
    events = EVENTS.copy()
    if out_of_order:
        events[-2:] = events[-2:][::-1]
    if events != EVENTS:
        raise ValueError('Saved processing precedes Native owner release')
    return {'events': events, 'fixture_only': True, 'actual_native_capture': False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--case')
    parser.add_argument('--kind')
    parser.add_argument('--output')
    parser.add_argument('--lifecycle', action='store_true')
    parser.add_argument('--out-of-order', action='store_true')
    args = parser.parse_args()
    result = lifecycle(args.out_of_order) if args.lifecycle else evaluate(args.case, args.kind)
    if args.output:
        Path(args.output).write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'passed': True, 'case_id': args.case, 'kind': args.kind,
                      'status': result.get('physical_checks', {}).get('maneuver', {}).get('status'),
                      'events': result.get('events')}))


if __name__ == '__main__':
    main()
