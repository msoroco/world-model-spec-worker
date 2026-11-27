"""Source-shaped saved proof for exact door/passing comparisons.

Synthetic color frames and annotations exercise joins only. They cannot
establish that a real door moved, a transfer happened, or traffic was impeded.
"""

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess

from finalize import finalize
from controller import CASES

ROOT = Path(__file__).resolve().parents[1]
VIEWS = ('overview', 'approach', 'reference_corner', 'driver_reference')


def write(path, value):
    path.write_text(json.dumps(value, sort_keys=True, allow_nan=False) + '\n')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def make(suffix):
    base = Path(os.environ['SCENARIO_PIPELINE_OUTPUT_ROOT']).resolve()
    base.mkdir(parents=True, exist_ok=True)
    folder = base / ('saved-fixture-' + suffix)
    if folder.exists():
        shutil.rmtree(folder)
    folder.mkdir()
    case = ROOT.name + '__' + suffix
    spec = CASES[suffix]
    config = json.loads((ROOT / 'cases' / suffix / 'config.json').read_text())
    write(folder / 'config.json', config)
    write(folder / 'original-map.json', {'map_name': 'Town03'})
    write(folder / 'original-road.json', {'map_name': 'Town03', 'door_side': 'left',
        'passing_side': 'left', 'frozen_cell': config['frozen_cell']})
    write(folder / 'original-transfer.json', {'kind': 'passenger', 'frame': 200,
        'pedestrian_actor_id': 3, 'occupancy_delta': spec['occupancy_delta']})
    sources = {name: {'path': 'synthetic fixture only',
        'sha256': sha(folder / ('original-' + name + '.json'))}
        for name in ('map', 'road', 'transfer')}
    write(folder / 'original-scene-review.json', {'source_kind': 'source_bound_native_setup',
        'case_id': case, 'sources': sources})
    mapping, actors, trace = [], [], []
    for i in range(600):
        moving = spec['pass_start'] <= i <= spec['pass_start'] + 100
        x = -20.0 + 0.2 * max(0, min(100, i - spec['pass_start']))
        speed = 4.0 if moving else 0.0
        mapping.append({'video_frame': i, 'carla_frame': 1000 + i,
                        'native_frame': 1000 + i, 'time_s': i/20,
                        'native_elapsed_s': 12 + i/20})
        actors.append({'video_frame': i, 'native_frame': 1000 + i,
            'native_elapsed_s': 12 + i/20, 'driver_actor_id': 1,
            'passing_actor_id': 2, 'pedestrian_actor_id': 3,
            'cargo_actor_id': None, 'ego_speed_mps': 0.0,
            'passing_position_m': [x, 2.0, 0.0],
            'passing_velocity_mps': [speed, 0.0, 0.0],
            'passing_speed_mps': speed, 'passing_radius_m': 1.0,
            'passing_lateral_offset_m': 2.0,
            'door_state_observed': None, 'occupancy_delta_observed': None,
            'requested': {'door_command': 'open' if 100 <= i < 212 else 'closed'}})
        trace.append({'frame': 1000+i, 'time_s': i/20,
            'position': {'x': 0, 'y': 0, 'z': 0},
            'heading_deg': 0, 'speed_mps': 0})
    for filename, rows in (('video_frames.jsonl', mapping), ('native-door-trace.jsonl', actors), ('trace.jsonl', trace)):
        (folder / filename).write_text(''.join(json.dumps(row, allow_nan=False) + '\n' for row in rows))
    video = folder / 'overview.mkv'
    subprocess.run(['ffmpeg', '-nostdin', '-hide_banner', '-loglevel', 'error', '-n',
        '-f', 'lavfi', '-i', 'color=c=blue:s=16x16:r=20', '-frames:v', '600',
        '-c:v', 'ffv1', str(video)], check=True, timeout=120)
    for name in VIEWS[1:]:
        shutil.copyfile(video, folder / (name + '.mkv'))
    observations = [{'video_frame': i, 'door_open': 100 <= i < 212,
        'source_camera': 'overview', 'pixel_box_xyxy': [1, 1, 8, 8],
        'hinge_world_xy_m': [0.0, 0.0], 'tip_world_xy_m': [0.0, 1.5]}
        for i in range(600)]
    write(folder / 'door-pixel-review.json', {'format': 'c228817-door-pixel-review-v1',
        'case_id': case, 'observed_traffic_side': 'left', 'observed_door_side': 'left',
        'ground_plane_calibration_source': 'synthetic calibration only',
        'camera_sha256': {name: sha(folder / (name + '.mkv')) for name in VIEWS},
        'door_observations': observations,
        'transfer_events': [{'kind': 'passenger', 'video_frame': 200,
            'source_camera': 'overview', 'pixel_box_xyxy': [1, 1, 8, 8],
            'occupancy_delta_observed': spec['occupancy_delta']}]})
    return folder


def prove():
    positive = []
    for suffix in CASES:
        folder = make(suffix)
        report = finalize(folder, folder / 'analysis.json')
        measured = report['measurements']['interference_context']['value']
        assert measured['door_open_frames'] == 112
        assert measured['person_transfer_frames'] == 1
        assert measured['moving_passing_traffic_frames'] == 101
        opening_only = measured['opening_only_before_transfer']
        assert opening_only['frame_range'] == [100, 199]
        assert opening_only['moving_traffic_observed_frames'] == (90 if suffix.endswith('overlap') else 0)
        assert opening_only['legal_interference_conclusion'] is None
        assert measured['legal_interference_conclusion'] is None
        positive.append({'case_id': report['case_id'], 'door_open_frames': 112,
                         'moving_passing_traffic_frames': 101,
                         'legal_interference_conclusion': None})
        # A missing original review must fail even with a complete command trace.
        (folder / 'analysis.json').unlink()
        (folder / 'result.json').unlink()
        (folder / 'door-pixel-review.json').unlink()
        try:
            finalize(folder, folder / 'missing.json')
        except ValueError as error:
            assert 'Missing required source: door-pixel-review.json' in str(error)
        else:
            raise AssertionError('missing review accepted')
    return {'format': 'source-shaped-door-interference-proof-v1',
            'positive_cases': positive, 'missing_source_rejected': True,
            'physical_verified': False, 'legal_verdict_claimed': False}


if __name__ == '__main__':
    print(json.dumps(prove(), sort_keys=True))
