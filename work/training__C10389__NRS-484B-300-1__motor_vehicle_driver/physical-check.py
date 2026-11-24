"""Measure diagnostic device response and reject missing body evidence.

This checker is reusable on an original attempt, but the bundled proof inputs are
synthetic CPU fixtures and confer no Native or statutory outcome.
"""
import argparse
import json
from pathlib import Path

FRAMES = 600
STATION = 50.0
ORDER = ['capture_finished', 'encoders_closed', 'restoration_verified',
         'native_exit', 'owner_released', 'saved_processing_started']


def evaluate(root, case_id):
    root = Path(root)
    actor_path = root / 'native-raw-actors.jsonl'
    map_path = root / 'native-map-readback.json'
    frame_path = root / 'video_frames.jsonl'
    sources = ['native-raw-actors.jsonl', 'native-map-readback.json', 'video_frames.jsonl']
    status = 'unverified'
    measured = {}
    if actor_path.is_file() and map_path.is_file() and frame_path.is_file():
        actors = [json.loads(line) for line in actor_path.read_text().splitlines() if line]
        frames = [json.loads(line) for line in frame_path.read_text().splitlines() if line]
        mapping = json.loads(map_path.read_text())
        if (len(actors) != FRAMES or len(frames) != FRAMES
                or mapping.get('stop_landmark_readback', {}).get('s_m') != STATION):
            raise ValueError('Device source or frame window differs')
        stopped = crossing = 0
        for i, (actor, frame) in enumerate(zip(actors, frames)):
            if (actor['frame'] != i or frame['video_frame'] != i
                    or actor['native_frame'] != frame['native_frame']
                    or abs(actor['time_s'] - frame['time_s']) > 1e-6):
                raise ValueError('Actor/video frame join differs')
            vertices = actor['ego']['body_native_xyz_m']
            if len(vertices) != 8:
                raise ValueError('Ego body vertices absent')
            front = max(v[0] for v in vertices)
            if front < STATION and actor['ego']['speed_mps'] < .1:
                stopped += 1
            if front >= STATION:
                crossing += 1
        measured = {'stopped_before_frames': stopped, 'body_at_station_frames': crossing}
        if case_id.endswith('__probe_1'):
            status = 'met' if stopped >= 20 else 'not_met'
        elif case_id.endswith('__probe_2'):
            status = 'met' if crossing > 0 and stopped == 0 else 'not_met'
        else:
            raise ValueError('Unknown device-response case')
    return {'case_id': case_id,
            'physical_checks': {'maneuver': {'status': status,
                'method': '600-frame original-identity body/velocity and device-station joins',
                'sources': sources}},
            'maneuver_completed': status == 'met',
            'realized_observables': measured if status == 'met' else {},
            'provenance_kind': 'synthetic_fixture', 'diagnostic_fixture': True,
            'physical_acceptance_claimed': False, 'legal_verdict_claimed': False}


def lifecycle(events):
    if events != ORDER:
        raise ValueError('Saved processing precedes Native ownership closure')
    return {'events': events, 'exit_code': 0, 'synthetic_fixture': True}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', type=Path)
    parser.add_argument('--case')
    parser.add_argument('--events', nargs='*')
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    value = lifecycle(args.events) if args.events is not None else evaluate(args.source, args.case)
    if args.output:
        args.output.write_text(json.dumps(value, indent=2) + '\n')
    print(json.dumps(value))
