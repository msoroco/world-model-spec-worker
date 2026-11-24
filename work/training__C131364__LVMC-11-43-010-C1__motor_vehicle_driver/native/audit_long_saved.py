"""Independent audit of source-bound synthetic saved rows and comparison."""
import argparse
import hashlib
import json
from pathlib import Path

CASE = Path(__file__).resolve().parents[1]
NAMES = ('overview', 'approach', 'reference_corner', 'driver_reference')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def require(ok, reason):
    if not ok:
        raise ValueError(reason)


def audit(source_root, saved_root):
    proof_path = CASE / 'native' / 'long-saved-proof.json'
    proof = json.loads(proof_path.read_text())
    require(proof['assignment_id'] == CASE.name and len(proof['positives']) == 2
            and {x['mutation'] for x in proof['negatives']} == {
                'altered_third_camera_frame_join', 'altered_lane_with_rebound_track_hash'}
            and proof['delivery_ready'] is False, 'saved proof scope differs')
    facts = []
    for witness, expected_lane in (('witness_1', -1), ('witness_2', -2)):
        source = source_root / witness
        saved = saved_root / witness
        manifest = json.loads((source / 'manifest.json').read_text())
        receipt = json.loads((saved / 'receipt.json').read_text())
        track = rows(source / 'requested-tracks.jsonl')
        values = rows(saved / 'source-bound-saved.jsonl')
        ledgers = {name: rows(source / (name + '-frames.jsonl')) for name in NAMES}
        require(len(track) == len(values) == 600
                and receipt['source_manifest_sha256'] == sha(source / 'manifest.json')
                and receipt['source_track_sha256'] == sha(source / 'requested-tracks.jsonl')
                and receipt['saved_sha256'] == sha(saved / 'source-bound-saved.jsonl')
                and receipt['source_video_sha256'] == manifest['video_sha256']
                and receipt['delivery_ready'] is False, 'source/saved binding differs')
        phases = []
        for index, (original, row) in enumerate(zip(track, values)):
            require(row['frame'] == index and row['time_s'] == original['time_s']
                    and row['requested_lane_id'] == original['lane_id'] == expected_lane
                    and row['requested_phase'] == original['phase']
                    and row['requested_road_id'] == original['road_id']
                    and row['source_track_sha256'] == manifest['track_sha256']
                    and row['source_kind'] == 'synthetic_cpu'
                    and row['observed_lane_id'] is None
                    and row['actual_exit_observed'] is False
                    and row['camera_pixels_reviewed'] is False
                    and row['physical_roundabout_verified'] is False
                    and row['legal_verdict'] is None,
                    'saved request/provenance differs at frame ' + str(index))
            require(set(row['source_cameras']) == set(NAMES),
                    'four saved camera names differ')
            for camera in NAMES:
                frame = ledgers[camera][index]
                join = row['source_cameras'][camera]
                require(join['source_frame'] == frame['video_frame'] == index
                        and join['source_native_frame'] == frame['native_frame'] == 1000 + index
                        and join['source_video_sha256'] == frame['video_sha256']
                        == manifest['video_sha256'][camera],
                        'saved camera/source join differs')
            phases.append(row['requested_phase'])
        require(set(phases) == {'entry', 'circulation', 'exit'} and
                phases == sorted(phases, key={'entry': 0, 'circulation': 1, 'exit': 2}.get),
                'saved source span differs')
        facts.append({'witness': witness, 'requested_lane_id': expected_lane,
                      'source_bound_frames': 600, 'source_bound_camera_joins': 2400,
                      'saved_sha256': receipt['saved_sha256']})
    require(facts[0]['requested_lane_id'] != facts[1]['requested_lane_id']
            and facts[0]['saved_sha256'] != facts[1]['saved_sha256'],
            'controlled requested-lane difference missing')
    return {'format': 'c131364-long-saved-independent-audit-v1',
            'assignment_id': CASE.name, 'proof_sha256': sha(proof_path),
            'facts': facts, 'source_kind': 'synthetic_cpu',
            'observed_lane_comparison': False, 'delivery_ready': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--source-root', type=Path, required=True)
    parser.add_argument('--saved-root', type=Path, required=True)
    args = parser.parse_args()
    result = audit(args.source_root, args.saved_root)
    path = CASE / 'native' / 'long-saved-audit.json'
    path.write_text(json.dumps(result, sort_keys=True, indent=2) + '\n')
    print(json.dumps({'witnesses': len(result['facts']),
                      'camera_joins': sum(x['source_bound_camera_joins'] for x in result['facts'])}))
