"""Saved Native bicycle geometry measurement; posture and legal meaning stay open."""
from __future__ import annotations

import math
import argparse
import hashlib
import json
from pathlib import Path
import subprocess


def measure(rider, native, mapping, sign):
    if sign.get('code') != 'no_u_turn' or sign.get('station_m') != 72.0:
        raise ValueError('Authored sign code or station differs from road')
    if not (len(rider) == len(native) == len(mapping) == 480):
        raise ValueError('Expected 480 joined source frames')
    actor = rider[0]['actor_id']
    xy = []
    headings = []
    lanes = []
    for i, (r, n, m) in enumerate(zip(rider, native, mapping)):
        if (r['frame'] != i or r['actor_id'] != actor or
            r['sign_id'] != sign['id'] or r['road_id'] != sign['governs_road'] or
            r['approach_lane_id'] != sign['governs_lane']):
            raise ValueError('Rider actor/sign/frame identity differs')
        if any(r.get(key) is not None for key in ('mounted', 'walking_machine', 'u_turn_active')):
            raise ValueError('Unreviewed posture or turn label was filled')
        if (n['native_frame'] != m['native_frame'] or
            m['video_frame'] != i or m['carla_frame'] != n['native_frame'] or
            n['time_s'] != m['time_s'] or r['time_s'] != n['time_s']):
            raise ValueError('Native/camera time or frame join differs')
        x, y = n['native_center_xy_m']
        if math.dist((x, y), (r['x_m'], r['y_m'])) > 1e-4:
            raise ValueError('Rider and Native centers differ')
        vx, vy = n['native_forward_xy']
        if not all(math.isfinite(v) for v in (x, y, vx, vy)) or not .99 <= math.hypot(vx, vy) <= 1.01:
            raise ValueError('Native position or heading invalid')
        if n['native_road_id'] != sign['governs_road']:
            raise ValueError('Native road differs from authored sign road')
        xy.append((x, y))
        headings.append((vx, vy))
        lanes.append(n['native_lane_id'])
    first = [sum(p[j] for p in headings[:20]) for j in (0, 1)]
    last = [sum(p[j] for p in headings[-20:]) for j in (0, 1)]
    denom = math.hypot(*first) * math.hypot(*last)
    if denom < 1:
        raise ValueError('Start or end heading evidence unstable')
    heading_change = math.degrees(math.acos(max(-1, min(1, (first[0]*last[0]+first[1]*last[1])/denom))))
    center_frames = sum(abs(y) < 1 and -12 <= x <= 12 for x, y in xy)
    switched = lanes[0] == sign['governs_lane'] and lanes[-1] == -sign['governs_lane']
    geometry_turn = heading_change >= 150 and switched and center_frames >= 5
    return {'frames': 480, 'actor_id': actor, 'start_lane_id': lanes[0],
            'end_lane_id': lanes[-1], 'heading_change_deg': round(heading_change, 6),
            'center_crossing_frames': center_frames, 'opposing_lane_arrival': switched,
            'u_turn_geometry_observed': geometry_turn,
            'mounted_posture_observed': None, 'sign_authorization_proven': False,
            'legal_outcome': 'unresolved', 'accepted': False}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_rows(path):
    if not path.is_file():
        raise ValueError('Missing saved source: '+path.name)
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def video_stream(path):
    if not path.is_file():
        raise ValueError('Missing original camera: '+path.name)
    command = ['ffprobe', '-v', 'error', '-count_frames', '-select_streams', 'v:0',
               '-show_entries', 'stream=codec_name,width,height,nb_read_frames',
               '-of', 'json', str(path)]
    run = subprocess.run(command, text=True, stdout=subprocess.PIPE,
                         stderr=subprocess.PIPE, timeout=120)
    if run.returncode:
        raise ValueError('Original camera decode failed: '+path.name)
    streams = json.loads(run.stdout).get('streams', [])
    if len(streams) != 1:
        raise ValueError('Original camera stream count differs: '+path.name)
    return streams[0]


def qualify_original(attempt, output):
    """Write a geometry receipt only after sealed original-source verification."""
    root, target = Path(attempt), Path(output)
    if target.exists():
        raise ValueError('Retain prior geometry receipt; use a fresh output')
    manifest = json.loads((root/'rider-source-manifest.json').read_text())
    if manifest.get('source_kind') != 'original_native_capture_unreviewed' or not manifest.get('original_native_capture_executed'):
        raise ValueError('Original capture source kind is unproved')
    if any(manifest.get(name) for name in ('mounted_posture_verified',
                                           'turn_from_saved_geometry_verified',
                                           'official_sign_authorization_verified')):
        raise ValueError('Unreviewed original source claims verified labels')
    rider_path = root/'rider_native_samples.jsonl'
    sign_path = root/'authored-sign.json'
    if sha(rider_path) != manifest['rider_samples_sha256'] or sha(sign_path) != manifest['sign_sha256']:
        raise ValueError('Original rider or sign source hash differs')
    config = json.loads((root/'config.json').read_text())
    if manifest['case_suffix'] != config['case_suffix'] or manifest['candidate_id'] != config['candidate_id']:
        raise ValueError('Original source/candidate differs')
    capture = json.loads((root/'capture/manifest.json').read_text())
    if capture.get('frames') != 480 or not capture.get('extraction_confirmed'):
        raise ValueError('Original capture is not sealed for 480 frames')
    sign = json.loads(sign_path.read_text())
    survey = json.loads((root/'road_geometry.json').read_text())
    landmark = survey.get('landmark_readback', [])
    if (len(landmark) != 1 or landmark[0].get('id') != '1140080' or
            landmark[0].get('road_id') != sign['governs_road'] or
            abs(landmark[0].get('s_m', -1) - sign['station_m']) > .5):
        raise ValueError('Saved Native sign station readback differs')
    rider = read_rows(rider_path)
    native = read_rows(root/'native_samples.jsonl')
    mapping = read_rows(root/'video_frames.jsonl')
    geometry = measure(rider, native, mapping, sign)
    cameras = {}
    for spec in config['cameras']:
        name = spec['name']+'.mkv'
        stream = video_stream(root/name)
        expected = (spec['width'], spec['height'], 480, 'ffv1')
        observed = (stream.get('width'), stream.get('height'),
                    int(stream.get('nb_read_frames', -1)), stream.get('codec_name'))
        if observed != expected:
            raise ValueError('Original camera dimensions, frames or codec differ: '+name)
        cameras[name] = {'width': observed[0], 'height': observed[1],
                         'frames': observed[2], 'codec': observed[3],
                         'sha256': sha(root/name)}
    if len(cameras) != 4:
        raise ValueError('Four original cameras required')
    receipt = {'format': 'c104538-original-saved-geometry-v1',
               'case_id': config['case_id'], 'candidate_id': config['candidate_id'],
               'measurement': geometry, 'cameras': cameras,
               'source_sha256': {name: sha(root/name) for name in
                   ('rider-source-manifest.json', 'rider_native_samples.jsonl',
                    'authored-sign.json', 'native_samples.jsonl',
                    'video_frames.jsonl', 'capture/manifest.json',
                    'road_geometry.json')},
               'original_native_capture_executed': True,
               'mounted_posture_observed': None,
               'sign_authorization_proven': False,
               'legal_verdict_claimed': False, 'accepted': False}
    target.write_text(json.dumps(receipt, indent=2, sort_keys=True)+'\n')
    return receipt


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    print(json.dumps(qualify_original(args.attempt, args.output)))
