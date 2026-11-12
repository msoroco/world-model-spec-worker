"""Synthetic source-joined turn outcome and Native-owner lifecycle CPU protocol."""
import argparse
from hashlib import sha256
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from turn_geometry import measure

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
EVENTS = ['capture_finished', 'encoders_closed', 'restoration_verified',
          'native_exit', 'owner_released', 'saved_processing_started']


def digest(path):
    return sha256(Path(path).read_bytes()).hexdigest()


def rows(text):
    return [json.loads(line) for line in text.splitlines() if line.strip()]


def evaluate(case, kind):
    manifest = json.loads((HERE / 'execution-manifest.json').read_text())
    entry = next((x for x in manifest['cases'] if x['case_id'] == case), None)
    if entry is None or kind not in ('complete_motion', 'incomplete_motion', 'missing_evidence'):
        raise ValueError('Unknown exact turn case or physical fixture kind')
    construction = HERE / entry['construction']
    if digest(construction) != entry['construction_sha256']:
        raise ValueError('Exact turn construction changed')
    recipe = json.loads((ROOT / entry['fixture_recipe']).read_text())
    source = ROOT / recipe['sources'][0]['source']
    if digest(source) != recipe['sources'][0]['sha256']:
        raise ValueError('Diagnostic source recipe changed')
    diagnostic = json.loads(source.read_text())
    files = diagnostic['files']
    required = ('road_geometry.json', 'body_footprints.json', 'body_footprints.jsonl',
                'video_frames.jsonl', 'trace.jsonl')
    if any(not isinstance(files.get(name), str) or not files[name] for name in required):
        raise ValueError('Original-shaped map/body/frame source absent')
    frame_map, footprints, trace = (rows(files[name]) for name in
                                    ('video_frames.jsonl', 'body_footprints.jsonl', 'trace.jsonl'))
    body = json.loads(files['body_footprints.json'])
    if not frame_map or len(frame_map) != len(footprints) or not trace:
        raise ValueError('Original-shaped source frame coverage differs')
    by_frame = {x['frame']: x for x in footprints}
    if len(by_frame) != len(footprints) or len(body['frames']) != len(footprints):
        raise ValueError('Original body footprint frame coverage differs')
    phases = set()
    for i, (frame, point) in enumerate(zip(frame_map, footprints)):
        if (frame['video_frame'] != i or point['frame'] != frame['carla_frame']
                or point['time_s'] != frame['time_s'] or point['subject_id'] != body['subject_id']
                or point != by_frame[frame['carla_frame']]
                or point != body['frames'][i]):
            raise ValueError('Original-shaped map/body/frame join differs')
        phases.add(point['phase'])
    if not {'approach', 'leaving_intersection'} <= phases:
        raise ValueError('Original approach and departure phases absent')
    if any(x['frame'] not in {f['carla_frame'] for f in frame_map} for x in trace):
        raise ValueError('Original trace frame join differs')
    with TemporaryDirectory(prefix='c228670-physical-') as temp:
        temp = Path(temp)
        geometry = temp / 'road_geometry.json'
        body_path = temp / 'body_footprints.json'
        geometry.write_text(files['road_geometry.json'])
        if kind == 'missing_evidence':
            observed = None
            status = 'unverified'
        else:
            variant = json.loads(files['body_footprints.json'])
            if kind == 'incomplete_motion':
                variant['frames'] = [row for row in variant['frames']
                                     if row['phase'] != 'leaving_intersection']
                body_path.write_text(json.dumps(variant))
                try:
                    measure(geometry, body_path)
                except ValueError as error:
                    if 'phases absent' not in str(error):
                        raise
                else:
                    raise ValueError('Incomplete departure fixture was accepted')
                observed, status = None, 'not_met'
            else:
                body_path.write_text(files['body_footprints.json'])
                observed = measure(geometry, body_path)
                if observed['approach_frame_ids'] != [row['frame'] for row in body['frames'] if row['phase'] == 'approach']:
                    raise ValueError('Measured approach source frames differ')
                if observed['departure_frame_ids'] != [row['frame'] for row in body['frames'] if row['phase'] == 'leaving_intersection']:
                    raise ValueError('Measured departure source frames differ')
                status = 'met'
    source_hashes = {name: sha256(files[name].encode()).hexdigest() for name in required}
    return {'format': 'worker-physical-fixture-outcome', 'case_id': case,
            'fixture_kind': kind, 'fixture_only': True, 'diagnostic_fixture': True,
            'actual_native_capture': False,
            'physical_checks': {'maneuver': {'status': status,
                'method': 'original-shaped map, four-corner body and synchronized frame join; no practicability or legal cutoff',
                'sources': {'construction': entry['construction'],
                            'construction_sha256': entry['construction_sha256'],
                            'diagnostic': recipe['sources'][0]['source'],
                            'diagnostic_sha256': digest(source),
                            'frame_count': len(frame_map), 'source_sha256': source_hashes},
                'missing_evidence': ['body_footprints.json'] if kind == 'missing_evidence' else []}},
            'maneuver_completed': status == 'met',
            'realized_observables': {'approach_left_curb_nearest_m': observed['approach_left_curb_nearest_m'],
                                     'departure_centerline_min_signed_m': observed['departure_centerline_min_signed_m'],
                                     'departure_centerline_max_signed_m': observed['departure_centerline_max_signed_m'],
                                     'departure_all_corners_right_of_centerline': observed['departure_all_corners_right_of_centerline']}
                                    if observed else {},
            'provenance_kind': 'native',
            'provenance_note': 'Native-shaped synthetic protocol only; no CARLA, practicability or legal completion',
            'physical_acceptance_claimed': False, 'legal_acceptance_claimed': False}


def lifecycle(out_of_order=False):
    events = EVENTS.copy()
    if out_of_order:
        events[3], events[4] = events[4], events[3]
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
