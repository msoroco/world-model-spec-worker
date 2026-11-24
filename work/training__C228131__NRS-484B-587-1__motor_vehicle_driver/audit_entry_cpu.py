"""Independent audit of the two synthetic controlled-entry source packets."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

CASE = Path(__file__).resolve().parent
NAMES = ('overview', 'approach', 'indicated_gate', 'highway_side')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def require(ok, reason):
    if not ok:
        raise ValueError(reason)


def audit(root):
    proof_path = CASE / 'entry-cpu-proof.json'
    proof = json.loads(proof_path.read_text())
    require(proof['assignment_id'] == CASE.name and len(proof['positives']) == 2
            and {x['mutation'] for x in proof['negatives']} == {
                'fourth_camera_frame_join', 'route_changed_with_rebound_hash'}
            and proof['delivery_ready'] is False, 'proof scope differs')
    facts = []
    for witness, expected_x in (('witness_1', 0), ('witness_2', 60)):
        folder = root / witness
        manifest = json.loads((folder / 'manifest.json').read_text())
        require(manifest['witness'] == witness and manifest['source_kind'] == 'synthetic_cpu'
                and manifest['frames'] == 600 and manifest['duration_s'] == 30
                and tuple(manifest['cameras']) == NAMES
                and manifest['input_sha256'] == sha(CASE.parents[1] / 'inputs' / CASE.name / 'assignment.json')
                and manifest['original_native_observed'] is False,
                'source manifest differs')
        track_path = folder / 'requested-track.jsonl'
        track = rows(track_path)
        require(len(track) == 600 and sha(track_path) == manifest['track_sha256'],
                'source track differs')
        crossing = []
        for index, row in enumerate(track):
            x, y = row['center_xy_m']
            require(row['video_frame'] == index and row['native_frame'] == 1000 + index
                    and row['time_s'] == index / 20
                    and row['source_kind'] == 'authored_native_request'
                    and row['actual_entry_observed'] is False
                    and row['official_device_verified'] is False
                    and x >= expected_x - 16 and x <= expected_x + 64,
                    'source route identity/timing differs')
            if index and track[index-1]['center_xy_m'][1] - .9 < 0 <= y - .9:
                crossing.append((index, x))
        require(len(crossing) == 1 and crossing[0][1] == expected_x,
                'entry crossing differs')
        for camera in NAMES:
            video = folder / (camera + '.mkv')
            require(sha(video) == manifest['video_sha256'][camera],
                    'source video byte hash differs')
            result = subprocess.run(['ffprobe', '-v', 'error', '-count_frames',
                                     '-select_streams', 'v:0', '-show_entries',
                                     'stream=codec_name,nb_read_frames', '-of', 'json', str(video)],
                                    capture_output=True, text=True, timeout=120)
            require(result.returncode == 0, 'source video decode failed')
            streams = json.loads(result.stdout)['streams']
            require(len(streams) == 1 and streams[0]['codec_name'] == 'ffv1'
                    and int(streams[0]['nb_read_frames']) == 600,
                    'source video frame count differs')
            ledger = rows(folder / (camera + '-frames.jsonl'))
            require(len(ledger) == 600, 'source camera ledger incomplete')
            for index, frame in enumerate(ledger):
                require(frame['video_frame'] == index
                        and frame['native_frame'] == 1000 + index
                        and frame['time_s'] == track[index]['time_s']
                        and frame['camera'] == camera
                        and frame['video_sha256'] == manifest['video_sha256'][camera]
                        and frame['source_kind'] == 'synthetic_cpu',
                        'source camera join differs')
        facts.append({'witness': witness, 'requested_crossing_frame': crossing[0][0],
                      'requested_crossing_x_m': crossing[0][1],
                      'source_bound_camera_joins': 2400,
                      'manifest_sha256': sha(folder / 'manifest.json')})
    return {'format': 'c228131-independent-entry-cpu-audit-v1',
            'assignment_id': CASE.name, 'proof_sha256': sha(proof_path),
            'facts': facts, 'source_kind': 'synthetic_cpu',
            'original_native_observed': False, 'delivery_ready': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--source-root', type=Path, required=True)
    args = parser.parse_args()
    result = audit(args.source_root)
    path = CASE / 'entry-cpu-audit.json'
    path.write_text(json.dumps(result, sort_keys=True, indent=2) + '\n')
    print(json.dumps({'witnesses': len(result['facts']), 'camera_joins': 4800}))
