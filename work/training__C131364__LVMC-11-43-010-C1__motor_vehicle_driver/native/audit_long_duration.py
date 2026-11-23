"""Independently inspect the 30-second synthetic source packet."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import subprocess


CASE = Path(__file__).resolve().parents[1]
NAMES = ('overview', 'approach', 'reference_corner', 'driver_reference')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines()]


def require(ok, message):
    if not ok:
        raise ValueError(message)


def audit(root):
    proof = json.loads((CASE / 'native' / 'long-duration-proof.json').read_text())
    require(proof['assignment_id'] == CASE.name and len(proof['positives']) == 2 and
            {row['mutation'] for row in proof['negatives']} == {
                'changed_fourth_camera_join', 'changed_second_camera_hash',
                'changed_route_with_rebound_hash'}, 'proof shape differs')
    facts = []
    for witness, lane in (('witness_1', -1), ('witness_2', -2)):
        folder = root / witness
        manifest = json.loads((folder / 'manifest.json').read_text())
        require(manifest['witness'] == witness and manifest['source_kind'] == 'synthetic_cpu'
                and manifest['frames'] == 600 and manifest['duration_s'] == 30
                and manifest['rate_hz'] == 20 and tuple(manifest['cameras']) == NAMES
                and manifest['delivery_ready'] is False, 'source scope differs')
        track = rows(folder / 'requested-tracks.jsonl')
        require(len(track) == 600 and sha(folder / 'requested-tracks.jsonl') ==
                manifest['track_sha256'], 'track coverage/hash differs')
        phase_ids = {'entry': 10, 'circulation': 11, 'exit': 12}
        counts = dict.fromkeys(phase_ids, 0)
        last = -1
        radius = 23.75 if witness == 'witness_1' else 27.25
        for i, row in enumerate(track):
            phase = row['phase']; number = tuple(phase_ids).index(phase)
            require(row['frame'] == i and row['time_s'] == (i + 1) / 20
                    and row['lane_id'] == lane and row['road_id'] == phase_ids[phase]
                    and number >= last and row['source_kind'] == 'authored_native_request'
                    and row['actual_exit_observed'] is False
                    and row['roundabout_verified'] is False,
                    'route frame, lane or provenance differs')
            if phase == 'circulation':
                require(abs(math.hypot(row['ego_x_m'], row['ego_y_m']) - radius) < .00001,
                        'circulating radial position differs')
            if phase == 'exit':
                require(0 <= row['ego_y_m'] <= 20.00001,
                        'exit continuation exceeds authored road budget')
            counts[phase] += 1
            last = number
        require(all(counts.values()), 'entry, circulation and exit coverage incomplete')
        for camera in NAMES:
            video = folder / (camera + '.mkv')
            require(sha(video) == manifest['video_sha256'][camera],
                    'camera byte binding differs')
            command = ['ffprobe', '-v', 'error', '-count_frames', '-select_streams', 'v:0',
                       '-show_entries', 'stream=codec_name,nb_read_frames', '-of', 'json', str(video)]
            process = subprocess.run(command, capture_output=True, text=True, timeout=120)
            require(process.returncode == 0, 'camera decode failed')
            stream = json.loads(process.stdout)['streams'][0]
            require(stream['codec_name'] == 'ffv1' and int(stream['nb_read_frames']) == 600,
                    'camera codec/count differs')
            ledger = rows(folder / (camera + '-frames.jsonl'))
            require(len(ledger) == 600, 'camera frame ledger incomplete')
            for i, frame in enumerate(ledger):
                require(frame['video_frame'] == i and frame['native_frame'] == 1000 + i
                        and frame['time_s'] == track[i]['time_s']
                        and frame['camera'] == camera
                        and frame['video_sha256'] == manifest['video_sha256'][camera]
                        and frame['source_kind'] == 'synthetic_cpu',
                        'camera frame join differs')
        facts.append({'witness': witness, 'lane_id': lane,
                      'phase_frames': counts, 'four_decoded_camera_frames': 2400,
                      'manifest_sha256': sha(folder / 'manifest.json')})
    return {'format': 'c131364-long-duration-independent-audit-v1',
            'assignment_id': CASE.name, 'proof_sha256': sha(CASE / 'native' / 'long-duration-proof.json'),
            'facts': facts, 'source_kind': 'synthetic_cpu',
            'original_native_observed': False, 'delivery_ready': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('--output-root', type=Path, required=True)
    args = parser.parse_args()
    result = audit(args.output_root)
    path = CASE / 'native' / 'long-duration-audit.json'
    path.write_text(json.dumps(result, indent=2, sort_keys=True) + '\n')
    print(json.dumps({'witnesses': len(result['facts']),
                      'decoded_frames': sum(x['four_decoded_camera_frames'] for x in result['facts'])}))
