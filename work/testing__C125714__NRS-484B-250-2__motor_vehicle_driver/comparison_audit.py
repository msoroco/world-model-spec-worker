"""Independent source comparison for the C125714 right/left approach pair."""

import hashlib
import json
from pathlib import Path

from entry_measurements import analyze

RIGHT = 'source_verified_other_right_near_time'
LEFT = 'source_verified_other_left_near_time'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def check(right, left, expected_frames=60):
    right, left = Path(right), Path(left)
    configs = [json.loads((root / 'config.json').read_text()) for root in (right, left)]
    if [c['selected_case_id'].rsplit('__', 1)[-1] for c in configs] != [RIGHT, LEFT]:
        raise ValueError('Right/left exact case identity differs')
    for key in ('law_id', 'cell_id', 'actor', 'rate_hz', 'duration_s', 'cameras',
                'required_atoms', 'source_packets', 'recording_description',
                'ego_target_speed_mps', 'other_target_speed_mps', 'other_release_frame'):
        if configs[0].get(key) != configs[1].get(key):
            raise ValueError('Fixed comparison config changed: ' + key)
    fixed_files = ('video_frames.jsonl', 'controller_history.jsonl', 'trace.jsonl',
                   'overview.mkv', 'approach.mkv', 'reference_corner.mkv',
                   'driver_reference.mkv')
    for name in fixed_files:
        if sha(right / name) != sha(left / name):
            raise ValueError('Fixed source changed: ' + name)
    geometry = [json.loads((root / 'road_geometry.json').read_text())
                for root in (right, left)]
    for key in ('intersection_polygon_xy_m', 'intersection_id', 'ego_highway_id',
                'other_highway_id', 'device_inventory_source', 'device_review',
                'ego_approach_heading_deg', 'ego_approach_origin_xy_m'):
        if geometry[0][key] != geometry[1][key]:
            raise ValueError('Fixed crossing geometry changed: ' + key)
    if (geometry[0]['other_approach_origin_xy_m'][1]
            != -geometry[1]['other_approach_origin_xy_m'][1]
            or geometry[0]['other_approach_heading_deg'] != -geometry[1]['other_approach_heading_deg']):
        raise ValueError('Other approach was not mirrored')
    histories = [rows(root / 'crossing_history.jsonl') for root in (right, left)]
    if len(histories[0]) != expected_frames or len(histories[1]) != expected_frames:
        raise ValueError('Comparison lacks all expected original diagnostic frames')
    for a, b in zip(*histories):
        if a['frame'] != b['frame'] or a['time_s'] != b['time_s'] or a['ego'] != b['ego']:
            raise ValueError('Fixed ego history changed')
        ao, bo = a['other'], b['other']
        if (ao['position_xy_m'][0] != bo['position_xy_m'][0]
                or ao['position_xy_m'][1] != -bo['position_xy_m'][1]
                or any(x != y or v != -w for (x, v), (y, w) in
                       zip(ao['body_vertices_xy_m'], bo['body_vertices_xy_m']))):
            raise ValueError('Other body history differs beyond reflected approach')
    reports = [analyze(root) for root in (right, left)]
    if ([r['other_is_to_ego_right'] for r in reports] != [True, False]
            or reports[0]['first_body_entry'] != reports[1]['first_body_entry']
            or reports[0]['ego_minus_other_entry_time_s'] != reports[1]['ego_minus_other_entry_time_s']):
        raise ValueError('Source-backed approach-side or entry-timing comparison failed')
    return {'format': 'worker-c125714-right-left-comparison',
            'case_ids': [c['selected_case_id'] for c in configs],
            'fixed_source_sha256': {name: sha(right / name) for name in fixed_files},
            'right_history_sha256': sha(right / 'crossing_history.jsonl'),
            'left_history_sha256': sha(left / 'crossing_history.jsonl'),
            'entry_delta_s': reports[0]['ego_minus_other_entry_time_s'],
            'frames': expected_frames,
            'other_right_by_case': [True, False],
            'software_comparison_passed': True,
            'physical_acceptance_claimed': False,
            'legal_priority_judgment': 'unresolved'}
