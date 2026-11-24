"""Convert the long synthetic source packet into provenance-safe saved rows.

The rows describe authored requests and camera synchronization, never observed
Native lane occupancy or reviewed pixels.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile

CASE = Path(__file__).resolve().parents[1]
NAMES = ('overview', 'approach', 'reference_corner', 'driver_reference')
FRAMES = 600


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def require(ok, message):
    if not ok:
        raise ValueError(message)


def save(path, data):
    path.write_text(json.dumps(data, sort_keys=True, indent=2) + '\n')


def prepare(source, output):
    require(not output.exists(), 'saved output must be fresh')
    manifest = json.loads((source / 'manifest.json').read_text())
    witness = manifest['witness']
    require(manifest['assignment_id'] == CASE.name and witness in ('witness_1', 'witness_2')
            and manifest['source_kind'] == 'synthetic_cpu' and manifest['frames'] == FRAMES
            and manifest['rate_hz'] == 20 and manifest['duration_s'] == 30
            and tuple(manifest['cameras']) == NAMES and manifest['delivery_ready'] is False
            and manifest['original_native_observed'] is False, 'source scope differs')
    track_file = source / 'requested-tracks.jsonl'
    track = rows(track_file)
    require(len(track) == FRAMES and sha(track_file) == manifest['track_sha256'],
            'source track hash or length differs')
    lane = -1 if witness == 'witness_1' else -2
    phases = {'entry': 10, 'circulation': 11, 'exit': 12}
    camera_rows = {}
    for camera in NAMES:
        video = source / (camera + '.mkv')
        require(sha(video) == manifest['video_sha256'][camera], 'camera hash differs: ' + camera)
        process = subprocess.run(['ffprobe', '-v', 'error', '-count_frames',
                                  '-select_streams', 'v:0', '-show_entries',
                                  'stream=codec_name,nb_read_frames', '-of', 'json', str(video)],
                                 capture_output=True, text=True, timeout=120)
        require(process.returncode == 0, 'camera probe failed: ' + camera)
        streams = json.loads(process.stdout).get('streams', [])
        require(len(streams) == 1 and streams[0]['codec_name'] == 'ffv1'
                and int(streams[0]['nb_read_frames']) == FRAMES,
                'camera decode count differs: ' + camera)
        camera_rows[camera] = rows(source / (camera + '-frames.jsonl'))
        require(len(camera_rows[camera]) == FRAMES, 'camera ledger length differs: ' + camera)
    saved = []
    phase_counts = dict.fromkeys(phases, 0)
    previous_phase = -1
    for i, request in enumerate(track):
        phase = request.get('phase')
        require(phase in phases, 'unknown route phase')
        phase_order = list(phases).index(phase)
        require(phase_order >= previous_phase and request.get('frame') == i
                and request.get('time_s') == (i + 1) / 20
                and request.get('source_kind') == 'authored_native_request'
                and request.get('witness') == witness
                and request.get('candidate_id') == 'primary'
                and request.get('lane_id') == lane
                and request.get('road_id') == phases[phase]
                and request.get('actual_exit_observed') is False
                and request.get('roundabout_verified') is False,
                'authored track continuity or scope differs at frame ' + str(i))
        joins = {}
        for camera in NAMES:
            frame = camera_rows[camera][i]
            require(frame == {'video_frame': i, 'native_frame': 1000 + i,
                              'time_s': (i + 1) / 20, 'camera': camera,
                              'video_sha256': manifest['video_sha256'][camera],
                              'source_kind': 'synthetic_cpu'},
                    'camera frame join differs: ' + camera + ':' + str(i))
            joins[camera] = {'source_frame': i, 'source_native_frame': 1000 + i,
                             'source_video_sha256': manifest['video_sha256'][camera]}
        saved.append({'frame': i, 'time_s': (i + 1) / 20,
                      'source_kind': 'synthetic_cpu', 'requested_lane_id': lane,
                      'requested_phase': phase, 'requested_road_id': phases[phase],
                      'source_track_sha256': manifest['track_sha256'],
                      'source_cameras': joins, 'observed_lane_id': None,
                      'actual_exit_observed': False, 'camera_pixels_reviewed': False,
                      'physical_roundabout_verified': False, 'legal_verdict': None})
        phase_counts[phase] += 1
        previous_phase = phase_order
    require(all(phase_counts.values()), 'entry/circulation/exit span incomplete')
    output.mkdir(parents=True)
    saved_file = output / 'source-bound-saved.jsonl'
    saved_file.write_text(''.join(json.dumps(row, sort_keys=True) + '\n' for row in saved))
    receipt = {'format': 'c131364-source-bound-synthetic-saved-v1',
               'assignment_id': CASE.name, 'witness': witness,
               'source_manifest_sha256': sha(source / 'manifest.json'),
               'source_track_sha256': manifest['track_sha256'],
               'source_video_sha256': manifest['video_sha256'],
               'saved_sha256': sha(saved_file), 'saved_frames': FRAMES,
               'camera_joins': FRAMES * len(NAMES), 'phase_frames': phase_counts,
               'source_kind': 'synthetic_cpu', 'original_native_observed': False,
               'camera_pixels_reviewed': False, 'physical_roundabout_verified': False,
               'delivery_ready': False}
    save(output / 'receipt.json', receipt)
    return receipt


def prove(source_root, output_root):
    require('.runtime-work' in source_root.resolve().parts and
            '.runtime-work' in output_root.resolve().parts,
            'source and saved output must be scratch')
    output_root.mkdir(parents=True, exist_ok=False)
    positive = [prepare(source_root / witness, output_root / witness)
                for witness in ('witness_1', 'witness_2')]
    require(all(sum(row['phase_frames'].values()) == FRAMES for row in positive)
            and positive[0]['source_track_sha256'] != positive[1]['source_track_sha256']
            and positive[0]['source_video_sha256'] != positive[1]['source_video_sha256'],
            'controlled source pair is not distinct with matching timing')
    negatives = []
    with tempfile.TemporaryDirectory(dir=output_root) as temporary:
        altered = Path(temporary) / 'source'
        shutil.copytree(source_root / 'witness_1', altered)
        path = altered / 'reference_corner-frames.jsonl'
        items = path.read_text().splitlines()
        row = json.loads(items[400]); row['native_frame'] += 1
        items[400] = json.dumps(row, sort_keys=True)
        path.write_text('\n'.join(items) + '\n')
        try:
            prepare(altered, Path(temporary) / 'rejected')
        except ValueError as error:
            negatives.append({'mutation': 'altered_third_camera_frame_join', 'error': str(error)})
        else:
            raise AssertionError('altered third camera join accepted')
    with tempfile.TemporaryDirectory(dir=output_root) as temporary:
        altered = Path(temporary) / 'source'
        shutil.copytree(source_root / 'witness_2', altered)
        path = altered / 'requested-tracks.jsonl'
        items = path.read_text().splitlines()
        row = json.loads(items[300]); row['lane_id'] = -1
        items[300] = json.dumps(row, sort_keys=True)
        path.write_text('\n'.join(items) + '\n')
        manifest_path = altered / 'manifest.json'
        manifest = json.loads(manifest_path.read_text())
        manifest['track_sha256'] = sha(path)
        save(manifest_path, manifest)
        try:
            prepare(altered, Path(temporary) / 'rejected')
        except ValueError as error:
            negatives.append({'mutation': 'altered_lane_with_rebound_track_hash', 'error': str(error)})
        else:
            raise AssertionError('altered requested lane accepted')
    proof = {'format': 'c131364-long-saved-proof-v1', 'assignment_id': CASE.name,
             'script_sha256': sha(__file__), 'positives': positive,
             'negatives': negatives, 'controlled_variable': 'requested_lane_id',
             'observed_lane_comparison': False, 'delivery_ready': False}
    save(CASE / 'native' / 'long-saved-proof.json', proof)
    return proof


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--source-root', type=Path, required=True)
    parser.add_argument('--output-root', type=Path, required=True)
    args = parser.parse_args()
    result = prove(args.source_root, args.output_root)
    print(json.dumps({'positives': len(result['positives']),
                      'negatives': len(result['negatives'])}))
