"""Source-bound roundabout exit-lane measurement; no legal classification."""
import argparse
import hashlib
import json
import math
import subprocess
from pathlib import Path

ASSIGNMENT = 'training__C131055__LVMC-11-43-010-C2__motor_vehicle_driver'
CAMERAS = ('forward', 'rear', 'left', 'right')
COUNT = 600


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def lines(path):
    return [json.loads(s) for s in path.read_text().splitlines() if s.strip()]


def finite(x):
    return type(x) in (int, float) and math.isfinite(x)


def measure(root):
    root = Path(root)
    paths = {n: root / n for n in ('video_frames.jsonl', 'native_lane_trace.jsonl', 'roundabout_topology.json')}
    for n, p in paths.items():
        if not p.is_file():
            raise ValueError('Missing saved source: ' + n)
    frames, trace = lines(paths['video_frames.jsonl']), lines(paths['native_lane_trace.jsonl'])
    topology = json.loads(paths['roundabout_topology.json'].read_text())
    if len(frames) != COUNT or len(trace) != COUNT:
        raise ValueError('Requires 600 joined original frames')
    if topology.get('assignment_id') != ASSIGNMENT or topology.get('review_kind') not in ('synthetic_diagnostic', 'original_source_review'):
        raise ValueError('Assignment or review provenance mismatch')
    hashes = {}
    for camera in CAMERAS:
        n = 'camera_' + camera + '.mkv'
        p = root / n
        if not p.is_file() or not p.stat().st_size:
            raise ValueError('Missing source camera: ' + camera)
        proc = subprocess.run(['ffprobe', '-v', 'error', '-count_frames', '-select_streams', 'v:0', '-show_entries',
                               'stream=nb_read_frames,r_frame_rate,width,height', '-of', 'json', str(p)],
                              capture_output=True, text=True)
        if proc.returncode:
            raise ValueError('Source camera decode failed: ' + camera)
        stream = json.loads(proc.stdout).get('streams', [])
        if len(stream) != 1 or stream[0].get('nb_read_frames') != str(COUNT) or stream[0].get('r_frame_rate') != '20/1':
            raise ValueError('Source camera is not 600 decoded 20 Hz frames: ' + camera)
        if topology['review_kind'] == 'original_source_review' and (stream[0].get('width'), stream[0].get('height')) != (1920, 1080):
            raise ValueError('Original camera resolution mismatch: ' + camera)
        hashes[n] = sha(p)
    if topology.get('camera_sha256') != hashes:
        raise ValueError('Topology is not bound to source camera bytes')
    for key in ('reviewer', 'map_topology_source', 'right_lane_adjacency_source', 'entry_exit_route_source',
                'intention_declaration_source', 'right_lane_id', 'left_lane_id', 'entry_road_id',
                'right_exit_road_id', 'intended_exit_road_id', 'roundabout_road_id'):
        if not topology.get(key):
            raise ValueError('Missing reviewed topology source: ' + key)
    right, left = topology['right_lane_id'], topology['left_lane_id']
    if right == left or topology['entry_road_id'] == topology['right_exit_road_id']:
        raise ValueError('Invalid circulatory lane or entry/exit topology')
    if topology['intended_exit_road_id'] != topology['right_exit_road_id']:
        raise ValueError('Declared intention is not the right exit')
    prev_native, prev_t = -1, -1.0
    roundabout, exited, lanes, headings, positions = [], [], [], [], []
    expected_kind = 'synthetic_native_sample' if topology['review_kind'] == 'synthetic_diagnostic' else 'original_native_pose'
    for i, (f, row) in enumerate(zip(frames, trace)):
        native, t = f.get('native_frame'), f.get('time_s')
        if f.get('video_frame') != i or type(native) is not int or native <= prev_native:
            raise ValueError('Invalid original frame identity')
        if not finite(t) or t <= prev_t or (i and abs(t - prev_t - .05) > .005):
            raise ValueError('Invalid original 20 Hz cadence')
        if row.get('video_frame') != i or row.get('native_frame') != native or row.get('source_kind') != expected_kind:
            raise ValueError('Native lane trace does not join original frame/provenance')
        for key in ('ego_x_m', 'ego_y_m', 'ego_heading_deg'):
            if not finite(row.get(key)):
                raise ValueError('Missing original pose: ' + key)
        lane, road = row.get('native_lane_id'), row.get('native_road_id')
        if not lane or not road:
            raise ValueError('Missing original map lane identity')
        inside = road == topology['roundabout_road_id']
        if inside and lane not in (right, left):
            raise ValueError('Circulatory lane lacks reviewed adjacency')
        roundabout.append(inside)
        exited.append(road == topology['right_exit_road_id'])
        lanes.append(lane)
        headings.append(row['ego_heading_deg'])
        positions.append((row['ego_x_m'], row['ego_y_m']))
        prev_native, prev_t = native, t
    if prev_t - frames[0]['time_s'] < 29.9:
        raise ValueError('Source span is less than 30 seconds')
    entries = [i for i in range(1, COUNT) if not roundabout[i-1] and roundabout[i]]
    exits = [i for i in range(1, COUNT) if roundabout[i-1] and exited[i]]
    if not entries or not exits or roundabout[0] or entries[0] >= exits[0]:
        raise ValueError('No complete roundabout entry-to-right-exit episode')
    entry, exit_frame = entries[0], exits[0]
    used = lanes[entry:exit_frame]
    changes = [entry + i for i in range(1, len(used)) if used[i] != used[i-1]]
    length = sum(math.hypot(positions[i][0]-positions[i-1][0], positions[i][1]-positions[i-1][1])
                 for i in range(entry+1, exit_frame+1))
    return {'format': 'saved-roundabout-exit-lane-observation', 'assignment_id': ASSIGNMENT,
            'review_kind': topology['review_kind'],
            'sources': {**{n: sha(p) for n, p in paths.items()}, **hashes},
            'sample_count': COUNT, 'sample_span_s': prev_t-frames[0]['time_s'],
            'entry_video_frame': entry, 'right_exit_video_frame': exit_frame,
            'intended_exit_matches_observed': topology['intended_exit_road_id'] == topology['right_exit_road_id'],
            'entry_lane_id': used[0], 'last_circulatory_lane_id': used[-1],
            'right_lane_id': right, 'right_lane_through_movement': all(lane == right for lane in used),
            'circulatory_lane_change_frames': changes, 'path_length_m': length,
            'entry_heading_deg': headings[entry], 'exit_heading_deg': headings[exit_frame],
            'physical_acceptance_claimed': False, 'legal_verdict_claimed': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('source_dir')
    parser.add_argument('output_json')
    args = parser.parse_args()
    Path(args.output_json).write_text(json.dumps(measure(args.source_dir), indent=2) + '\n')
