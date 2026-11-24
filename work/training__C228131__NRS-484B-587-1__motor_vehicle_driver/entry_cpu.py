"""Construct and test two 30-second controlled-access entry source packets.

These are authored trajectories with synthetic color videos. They exercise CPU
source joins and entry-event measurement; they are not Native observations.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import subprocess

CASE = Path(__file__).resolve().parent
CAMERAS = ('overview', 'approach', 'indicated_gate', 'highway_side')
FRAMES = 600
FPS = 20
GATE_X_M = 0.0
HIGHWAY_EDGE_Y_M = 0.0


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save(path, value):
    path.write_text(json.dumps(value, sort_keys=True, indent=2) + '\n')


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def require(ok, reason):
    if not ok:
        raise ValueError(reason)


def requested_pose(witness, frame):
    target_x = GATE_X_M if witness == 'witness_1' else 60.0
    t = frame / FPS
    if t < 8:
        x = target_x - 16 + 2 * t
        y = -9.0
        phase = 'approach'
    elif t < 14:
        x = target_x
        y = -9 + 2 * (t - 8)
        phase = 'enter'
    else:
        x = target_x + min(4 * (t - 14), 64)
        y = 3.0
        phase = 'highway'
    return {'video_frame': frame, 'native_frame': 1000 + frame,
            'time_s': t, 'source_kind': 'authored_native_request',
            'case_id': CASE.name + '__' + witness, 'vehicle_id': 'requested-ego',
            'phase': phase, 'center_xy_m': [round(x, 6), round(y, 6)],
            'footprint_half_width_m': .9, 'footprint_half_length_m': 2.2,
            'entry_gate_x_m': GATE_X_M, 'highway_edge_y_m': HIGHWAY_EDGE_Y_M,
            'actual_entry_observed': False, 'official_device_verified': False}


def decode_count(path):
    result = subprocess.run(['ffprobe', '-v', 'error', '-count_frames',
                             '-select_streams', 'v:0', '-show_entries',
                             'stream=codec_name,nb_read_frames', '-of', 'json', str(path)],
                            capture_output=True, text=True, timeout=120)
    require(result.returncode == 0, 'video probe failed: ' + result.stderr)
    streams = json.loads(result.stdout).get('streams', [])
    require(len(streams) == 1 and streams[0]['codec_name'] == 'ffv1', 'codec differs')
    return int(streams[0]['nb_read_frames'])


def build(folder, witness):
    folder.mkdir(parents=True, exist_ok=False)
    track_path = folder / 'requested-track.jsonl'
    track_path.write_text(''.join(json.dumps(requested_pose(witness, i), sort_keys=True) + '\n'
                                  for i in range(FRAMES)))
    video_hashes = {}
    for camera, color in zip(CAMERAS, ('red', 'green', 'blue', 'yellow')):
        path = folder / (camera + '.mkv')
        process = subprocess.run(['ffmpeg', '-nostdin', '-hide_banner', '-loglevel',
                                  'error', '-y', '-f', 'lavfi', '-i',
                                  f'color=c={color}:s=160x90:r={FPS}:d=30',
                                  '-frames:v', str(FRAMES), '-an', '-c:v', 'ffv1',
                                  '-level', '1', str(path)],
                                 capture_output=True, text=True, timeout=120)
        require(process.returncode == 0, 'synthetic video encode failed: ' + process.stderr)
        video_hashes[camera] = sha(path)
        ledger = folder / (camera + '-frames.jsonl')
        ledger.write_text(''.join(json.dumps({'camera': camera, 'video_frame': i,
            'native_frame': 1000 + i, 'time_s': i / FPS,
            'source_kind': 'synthetic_cpu', 'video_sha256': video_hashes[camera]},
            sort_keys=True) + '\n' for i in range(FRAMES)))
    save(folder / 'manifest.json', {'format': 'c228131-entry-source-v1',
        'assignment_id': CASE.name, 'witness': witness, 'frames': FRAMES,
        'rate_hz': FPS, 'duration_s': 30, 'cameras': list(CAMERAS),
        'track_sha256': sha(track_path), 'video_sha256': video_hashes,
        'input_sha256': sha(CASE.parents[1] / 'inputs' / CASE.name / 'assignment.json'),
        'case_plan_sha256': sha(CASE / 'case-plan.json'),
        'source_kind': 'synthetic_cpu', 'original_native_observed': False,
        'actual_pixels_reviewed': False, 'delivery_ready': False})


def measure(folder):
    manifest = json.loads((folder / 'manifest.json').read_text())
    witness = manifest['witness']
    require(manifest['assignment_id'] == CASE.name and witness in ('witness_1', 'witness_2')
            and manifest['source_kind'] == 'synthetic_cpu' and manifest['frames'] == FRAMES
            and tuple(manifest['cameras']) == CAMERAS and manifest['delivery_ready'] is False,
            'source scope differs')
    require(manifest['input_sha256'] == sha(CASE.parents[1] / 'inputs' / CASE.name / 'assignment.json')
            and manifest['case_plan_sha256'] == sha(CASE / 'case-plan.json'),
            'frozen input or plan source differs')
    track_path = folder / 'requested-track.jsonl'
    track = rows(track_path)
    require(len(track) == FRAMES and sha(track_path) == manifest['track_sha256'],
            'track count or hash differs')
    ledgers = {}
    for camera in CAMERAS:
        path = folder / (camera + '.mkv')
        require(sha(path) == manifest['video_sha256'][camera]
                and decode_count(path) == FRAMES, 'video hash/decode differs: ' + camera)
        ledgers[camera] = rows(folder / (camera + '-frames.jsonl'))
        require(len(ledgers[camera]) == FRAMES, 'camera ledger incomplete: ' + camera)
    crossing = []
    previous_inside = False
    for i, row in enumerate(track):
        require(row == requested_pose(witness, i), 'authored request differs: ' + str(i))
        for camera in CAMERAS:
            require(ledgers[camera][i] == {'camera': camera, 'video_frame': i,
                'native_frame': 1000 + i, 'time_s': i / FPS,
                'source_kind': 'synthetic_cpu',
                'video_sha256': manifest['video_sha256'][camera]},
                'camera frame join differs: ' + camera + ':' + str(i))
        x, y = row['center_xy_m']
        inside = y - row['footprint_half_width_m'] >= HIGHWAY_EDGE_Y_M
        if inside and not previous_inside:
            crossing.append({'frame': i, 'time_s': i / FPS,
                             'requested_center_x_m': x,
                             'at_indicated_gate_request': abs(x - GATE_X_M) <= 2.2})
        previous_inside = inside
    require(len(crossing) == 1, 'one requested entry event required')
    require(crossing[0]['at_indicated_gate_request'] is (witness == 'witness_1'),
            'controlled entry variable differs')
    return {'case_id': CASE.name + '__' + witness,
            'source_manifest_sha256': sha(folder / 'manifest.json'),
            'requested_track_sha256': sha(track_path),
            'camera_video_sha256': manifest['video_sha256'],
            'source_bound_camera_joins': FRAMES * len(CAMERAS),
            'requested_crossing': crossing[0], 'actual_entry_observed': False,
            'official_device_verified': False, 'legal_result': None,
            'source_kind': 'synthetic_cpu', 'delivery_ready': False}


def prove(root):
    require('.runtime-work' in root.resolve().parts, 'generated packet must stay under .runtime-work')
    root.mkdir(parents=True, exist_ok=False)
    positives = []
    for witness in ('witness_1', 'witness_2'):
        folder = root / witness
        build(folder, witness)
        positives.append(measure(folder))
    negatives = []
    path = root / 'witness_1' / 'highway_side-frames.jsonl'
    original = path.read_bytes(); lines = original.splitlines()
    row = json.loads(lines[360]); row['native_frame'] += 1
    lines[360] = json.dumps(row, sort_keys=True).encode()
    path.write_bytes(b'\n'.join(lines) + b'\n')
    try:
        measure(root / 'witness_1')
    except ValueError as error:
        negatives.append({'mutation': 'fourth_camera_frame_join', 'error': str(error)})
    else:
        raise AssertionError('changed camera join accepted')
    finally:
        path.write_bytes(original)
    path = root / 'witness_2' / 'requested-track.jsonl'
    manifest_path = root / 'witness_2' / 'manifest.json'
    original = path.read_bytes(); original_manifest = manifest_path.read_bytes()
    lines = original.splitlines(); row = json.loads(lines[250]); row['center_xy_m'][0] = 0
    lines[250] = json.dumps(row, sort_keys=True).encode()
    path.write_bytes(b'\n'.join(lines) + b'\n')
    changed = json.loads(original_manifest); changed['track_sha256'] = sha(path)
    save(manifest_path, changed)
    try:
        measure(root / 'witness_2')
    except ValueError as error:
        negatives.append({'mutation': 'route_changed_with_rebound_hash', 'error': str(error)})
    else:
        raise AssertionError('changed route accepted')
    finally:
        path.write_bytes(original); manifest_path.write_bytes(original_manifest)
    proof = {'format': 'c228131-entry-cpu-proof-v1', 'assignment_id': CASE.name,
             'script_sha256': sha(Path(__file__)), 'positives': positives,
             'negatives': negatives, 'original_native_observed': False,
             'official_device_verified': False, 'delivery_ready': False}
    save(CASE / 'entry-cpu-proof.json', proof)
    return proof


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output-root', type=Path, required=True)
    args = parser.parse_args()
    proof = prove(args.output_root)
    print(json.dumps({'positives': len(proof['positives']),
                      'negatives': len(proof['negatives'])}))
