"""Independent saved-source integrity audit; never grants physical/legal acceptance."""
import argparse
import hashlib
import json
from pathlib import Path


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read_rows(path):
    if not path.is_file():
        raise ValueError('Missing required source: ' + path.name)
    return [json.loads(s) for s in path.read_text().splitlines() if s.strip()]


def audit(root, case_id):
    root = Path(root)
    names = ['trace.jsonl', 'video_frames.jsonl', 'turn_history.jsonl',
             'approach_history.jsonl', 'visibility_history.jsonl']
    streams = {name: read_rows(root / name) for name in names}
    length = len(streams['trace.jsonl'])
    if length < 2 or any(len(rows) != length for rows in streams.values()):
        raise ValueError('Incomplete original frame histories')
    for index in range(length):
        marker = streams['video_frames.jsonl'][index]
        frame = marker['carla_frame']
        if marker['video_frame'] != index or any(
            row['frame'] != frame or abs(row['time_s'] - marker['time_s']) > 1e-4
            for name, rows in streams.items() if name != 'video_frames.jsonl'
            for row in [rows[index]]):
            raise ValueError('Original frame/time join differs')
        visibility = streams['visibility_history.jsonl'][index]['visibility']
        if visibility.get('probe_distance_m') != 152.4:
            raise ValueError('500-foot raw probe absent')
        approaches = visibility.get('approaches', [])
        if len(approaches) != 2 or len({a.get('lane_id') for a in approaches}) != 2:
            raise ValueError('Both incoming approaches absent')
        if any(len(a.get('body_rays_at_probe', [])) != 9 for a in approaches):
            raise ValueError('Nine body sample rays absent')
        if len(streams['turn_history.jsonl'][index].get('body_vertices_m', [])) < 4:
            raise ValueError('Subject body geometry absent')
        if len(streams['approach_history.jsonl'][index].get('body_vertices_m', [])) < 4:
            raise ValueError('Approaching body geometry absent')
    return {'format': 'worker-delivery-audit', 'case_id': case_id,
            'source_hashes': {name: sha(root / name) for name in names},
            'frames': length, 'checks': ['all_participants', 'time_join',
                                        'raw_500ft_two_directions', 'nine_body_samples'],
            'physical_completion_accepted': False,
            'actual_pixels_accepted': False, 'legal_judgment': 'unresolved'}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--case', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    Path(args.output).write_text(json.dumps(audit(args.attempt, args.case), indent=2) + '\n')


if __name__ == '__main__':
    main()
