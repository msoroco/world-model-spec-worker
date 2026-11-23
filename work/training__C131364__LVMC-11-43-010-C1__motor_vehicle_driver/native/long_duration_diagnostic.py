"""Build and verify 30-second synthetic roundabout source joins.

These authored requests and color videos test CPU capture plumbing only. They
are never Native observations, camera review, or statutory measurements.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import subprocess


HERE = Path(__file__).resolve().parent
CASE = HERE.parent
CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')
FRAMES = 600


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_json(path, data):
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + '\n')


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def require(condition, reason):
    if not condition:
        raise ValueError(reason)


def pose(witness, frame):
    radius = 23.75 if witness == 'witness_1' else 27.25
    lane = -1 if witness == 'witness_1' else -2
    time_s = (frame + 1) / 20
    arc = radius * math.pi / 2
    distance = min(6 * time_s, 30 + arc + 20)
    if distance < 30:
        phase, road, x, y, heading = 'entry', 10, -30 + distance, -radius, 0
    elif distance < 30 + arc:
        theta = -math.pi / 2 + (distance - 30) / radius
        phase, road = 'circulation', 11
        x, y, heading = radius * math.cos(theta), radius * math.sin(theta), math.degrees(theta + math.pi / 2)
    else:
        phase, road, x, y, heading = 'exit', 12, radius, distance - 30 - arc, 90
    return {'frame': frame, 'time_s': time_s, 'source_kind': 'authored_native_request',
            'witness': witness, 'candidate_id': 'primary', 'road_id': road,
            'lane_id': lane, 'phase': phase, 'ego_x_m': round(x, 6),
            'ego_y_m': round(y, 6), 'ego_heading_deg': round(heading, 6),
            'actual_exit_observed': False, 'roundabout_verified': False}


def create_video(path, color):
    command = ['ffmpeg', '-nostdin', '-hide_banner', '-loglevel', 'error', '-y',
               '-f', 'lavfi', '-i', f'color=c={color}:s=160x90:r=20:d=30',
               '-frames:v', str(FRAMES), '-an', '-c:v', 'ffv1', '-level', '1', str(path)]
    result = subprocess.run(command, capture_output=True, text=True, timeout=120)
    require(result.returncode == 0, 'synthetic FFV1 encode failed: ' + result.stderr)


def decode_count(path):
    command = ['ffprobe', '-v', 'error', '-count_frames', '-select_streams', 'v:0',
               '-show_entries', 'stream=codec_name,nb_read_frames', '-of', 'json', str(path)]
    result = subprocess.run(command, capture_output=True, text=True, timeout=120)
    require(result.returncode == 0, 'synthetic FFV1 probe failed: ' + result.stderr)
    streams = json.loads(result.stdout).get('streams', [])
    require(len(streams) == 1 and streams[0].get('codec_name') == 'ffv1', 'video codec differs')
    return int(streams[0]['nb_read_frames'])


def verify(folder):
    manifest = json.loads((folder / 'manifest.json').read_text())
    witness = manifest['witness']
    require(witness in ('witness_1', 'witness_2'), 'witness differs')
    require(manifest['source_kind'] == 'synthetic_cpu' and manifest['frames'] == FRAMES,
            'diagnostic scope differs')
    require(tuple(manifest['cameras']) == CAMERAS, 'four camera names differ')
    track_path = folder / 'requested-tracks.jsonl'
    track = rows(track_path)
    require(len(track) == FRAMES and manifest['track_sha256'] == digest(track_path),
            'track count or hash differs')
    phases = set()
    for frame, record in enumerate(track):
        require(record == pose(witness, frame), 'authored route differs at frame ' + str(frame))
        phases.add(record['phase'])
    require(phases == {'entry', 'circulation', 'exit'}, 'route lacks required phases')
    for camera in CAMERAS:
        video = folder / (camera + '.mkv')
        require(digest(video) == manifest['video_sha256'][camera], 'camera hash differs: ' + camera)
        require(decode_count(video) == FRAMES, 'camera decode count differs: ' + camera)
        ledger = rows(folder / (camera + '-frames.jsonl'))
        require(len(ledger) == FRAMES, 'camera ledger coverage differs: ' + camera)
        for frame, row in enumerate(ledger):
            require(row == {'video_frame': frame, 'native_frame': 1000 + frame,
                            'time_s': (frame + 1) / 20, 'camera': camera,
                            'video_sha256': manifest['video_sha256'][camera],
                            'source_kind': 'synthetic_cpu'},
                    'camera frame join differs: ' + camera + ':' + str(frame))
    return {'witness': witness, 'frames': FRAMES, 'phases': sorted(phases),
            'track_sha256': digest(track_path), 'video_sha256': manifest['video_sha256'],
            'all_four_decoded': True}


def build(folder, witness):
    folder.mkdir(parents=True, exist_ok=False)
    track_path = folder / 'requested-tracks.jsonl'
    track_path.write_text(''.join(json.dumps(pose(witness, frame), sort_keys=True) + '\n'
                                  for frame in range(FRAMES)))
    hashes = {}
    for camera, color in zip(CAMERAS, ('red', 'green', 'blue', 'yellow')):
        video = folder / (camera + '.mkv')
        create_video(video, color)
        hashes[camera] = digest(video)
        ledger = folder / (camera + '-frames.jsonl')
        ledger.write_text(''.join(json.dumps({'video_frame': frame,
            'native_frame': 1000 + frame, 'time_s': (frame + 1) / 20,
            'camera': camera, 'video_sha256': hashes[camera],
            'source_kind': 'synthetic_cpu'}, sort_keys=True) + '\n'
            for frame in range(FRAMES)))
    write_json(folder / 'manifest.json', {'format': 'c131364-long-diagnostic-v1',
        'assignment_id': CASE.name, 'witness': witness, 'source_kind': 'synthetic_cpu',
        'frames': FRAMES, 'rate_hz': 20, 'duration_s': 30, 'cameras': list(CAMERAS),
        'track_sha256': digest(track_path), 'video_sha256': hashes,
        'original_native_observed': False, 'actual_pixels_reviewed': False,
        'physical_roundabout_verified': False, 'delivery_ready': False})


def prove(output):
    positives = []
    for witness in ('witness_1', 'witness_2'):
        folder = output / witness
        build(folder, witness)
        positives.append(verify(folder))
    negatives = []
    folder = output / 'witness_1'
    ledger = folder / 'driver_reference-frames.jsonl'
    original = ledger.read_bytes()
    altered = original.splitlines()
    row = json.loads(altered[300]); row['native_frame'] += 1
    altered[300] = json.dumps(row, sort_keys=True).encode()
    ledger.write_bytes(b'\n'.join(altered) + b'\n')
    try:
        verify(folder)
    except ValueError as error:
        negatives.append({'mutation': 'changed_fourth_camera_join', 'error': str(error)})
    else:
        raise AssertionError('altered fourth camera join accepted')
    finally:
        ledger.write_bytes(original)
    manifest_path = folder / 'manifest.json'
    original = manifest_path.read_bytes(); changed = json.loads(original)
    changed['video_sha256']['approach'] = '0' * 64
    write_json(manifest_path, changed)
    try:
        verify(folder)
    except ValueError as error:
        negatives.append({'mutation': 'changed_second_camera_hash', 'error': str(error)})
    else:
        raise AssertionError('altered second camera hash accepted')
    finally:
        manifest_path.write_bytes(original)
    track_path = folder / 'requested-tracks.jsonl'
    original = track_path.read_bytes(); original_manifest = manifest_path.read_bytes()
    altered = original.splitlines()
    row = json.loads(altered[400]); row['phase'] = 'entry'
    altered[400] = json.dumps(row, sort_keys=True).encode()
    track_path.write_bytes(b'\n'.join(altered) + b'\n')
    changed = json.loads(manifest_path.read_text())
    changed['track_sha256'] = digest(track_path)
    write_json(manifest_path, changed)
    try:
        verify(folder)
    except ValueError as error:
        negatives.append({'mutation': 'changed_route_with_rebound_hash', 'error': str(error)})
    else:
        raise AssertionError('altered route accepted')
    finally:
        track_path.write_bytes(original)
        manifest_path.write_bytes(original_manifest)
    return {'format': 'c131364-long-duration-proof-v1',
            'assignment_id': CASE.name, 'script_sha256': digest(__file__),
            'positives': positives, 'negatives': negatives,
            'source_kind': 'synthetic_cpu', 'original_native_observed': False,
            'physical_roundabout_verified': False, 'delivery_ready': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('--output-root', type=Path, required=True)
    args = parser.parse_args()
    require('.runtime-work' in args.output_root.resolve().parts,
            'diagnostic output must be under .runtime-work')
    args.output_root.mkdir(parents=True, exist_ok=False)
    result = prove(args.output_root)
    write_json(HERE / 'long-duration-proof.json', result)
    print(json.dumps({'positives': len(result['positives']),
                      'negatives': len(result['negatives'])}))
