"""Audit original cone occupancy against the selected directed roadway source."""

import argparse
import hashlib
import json
from pathlib import Path


def _rows(path):
    if not path.is_file() or not path.read_bytes():
        raise ValueError('Missing required source: ' + path.name)
    rows = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    if not rows:
        raise ValueError('Closure original source is empty')
    return rows


def audit(attempt):
    attempt = Path(attempt)
    closure_path = attempt / 'closure_devices.jsonl'
    roadway_path = attempt / 'directed_roadway_footprints.jsonl'
    closure = _rows(closure_path)
    roadway = _rows(roadway_path)
    if len(closure) != len(roadway):
        raise ValueError('Closure and roadway original frame counts differ')
    ids = None
    initial_positions = None
    frames = []
    for cone_row, road in zip(closure, roadway):
        frame = cone_row['frame']
        if frame != road['frame'] or abs(cone_row['time_s'] - road['time_s']) > 1e-4:
            raise ValueError('Closure original frame/time join differs')
        if frames and (frame != frames[-1] + 1 or
                       abs(cone_row['time_s'] - closure[len(frames)-1]['time_s'] - .05) > 1e-4):
            raise ValueError('Closure original source not continuous at 20 Hz')
        frames.append(frame)
        if cone_row.get('authority_verified') is not False:
            raise ValueError('Closure source claims unproved authority')
        devices = cone_row.get('devices', [])
        if len(devices) != 3:
            raise ValueError('Closure requires three original cone actors')
        current_ids = [d['actor_id'] for d in devices]
        if len(set(current_ids)) != 3 or (ids is not None and current_ids != ids):
            raise ValueError('Closure original cone identity changed')
        ids = current_ids
        if any(not d['blueprint_id'].startswith('static.prop.trafficcone') for d in devices):
            raise ValueError('Closure original actor is not a cone')
        positions = [d['position_m'] for d in devices]
        if initial_positions is not None and any(
                sum((a-b)**2 for a,b in zip(p, q)) > .01
                for p,q in zip(positions, initial_positions)):
            raise ValueError('Closure cone moved from its original placement')
        initial_positions = positions if initial_positions is None else initial_positions
        center = road['roadway_center_point_xy']
        tangent = road['travel_tangent_xy']
        right = [-tangent[1], tangent[0]]
        width = road['subject_lane_width_m']
        if width <= 0:
            raise ValueError('Closure original lane width missing')
        offsets = [sum((p[i] - center[i]) * right[i] for i in (0,1)) for p in positions]
        if any(not 0 < offset < width for offset in offsets) or \
                max(offsets) - min(offsets) < width * .5:
            raise ValueError('Closure cones do not span the selected right half')
    return {'format': 'worker-closure-original-source-audit',
            'frames': frames, 'cone_actor_ids': ids,
            'closure_source_sha256': hashlib.sha256(closure_path.read_bytes()).hexdigest(),
            'roadway_source_sha256': hashlib.sha256(roadway_path.read_bytes()).hexdigest(),
            'authority_verified': False, 'delivery_ready': False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    Path(args.output).write_text(json.dumps(audit(args.attempt), indent=2) + '\n')


if __name__ == '__main__':
    main()
