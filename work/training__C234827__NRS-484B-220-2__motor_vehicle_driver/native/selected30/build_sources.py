"""Build assignment-bound 600-frame rotary delivery sources and CPU fixtures."""
import hashlib
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REPO = ROOT.parents[1]
NATIVE = Path(__file__).resolve().parent
ASSIGNMENT = json.loads((REPO / 'inputs' / ROOT.name / 'assignment.json').read_text())
CASES = {'reference': 1, 'contrast': -1}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')


def build(case):
    sign = CASES[case]
    folder = NATIVE / 'source' / case
    folder.mkdir(parents=True, exist_ok=True)
    case_id = ROOT.name + '__' + case
    source_assignment = REPO / 'inputs' / ROOT.name / 'assignment.json'
    (folder / 'assignment-source.json').write_bytes(source_assignment.read_bytes())
    road = ROOT / 'native' / 'selected30' / 'road.xodr'
    island = ROOT / 'native' / 'selected30' / 'island-geometry.json'
    rows = []
    for frame in range(600):
        theta = -math.pi / 2 + sign * 8 * (frame + 1) / 20 / 23.75
        rows.append({'case_id': case_id, 'frame': frame, 'time_s': (frame + 1) / 20,
                     'ego_x_m': round(23.75 * math.cos(theta), 6),
                     'ego_y_m': round(23.75 * math.sin(theta), 6),
                     'ego_heading_deg': round(math.degrees(theta + sign * math.pi / 2) % 360, 6),
                     'ego_speed_mps': 8.0, 'requested_radius_m': 23.75,
                     'requested_rotation_sign': sign,
                     'requested_unwrapped_angle_rad': round(theta, 9),
                     'island_center_xy_m': [0, 0], 'source_kind': 'authored_native_request',
                     'physical_island_verified': False})
    (folder / 'requested-tracks.jsonl').write_text(''.join(json.dumps(row, sort_keys=True) + '\n' for row in rows))
    cfg = {'format': 'c234827-nrs-island-delivery-v2',
           'assignment_id': ROOT.name, 'case_id': case_id, 'selected_case_id': case_id,
           'supported_case_ids': [case_id], 'candidate_id': 'primary',
           'law_id': ASSIGNMENT['law_id'], 'cell_id': ASSIGNMENT['cell_id'],
           'actor': ASSIGNMENT['actor'], 'frames': 600, 'rate_hz': 20, 'duration_s': 30,
           'requested_rotation_sign': sign, 'requested_speed_mps': 8.0,
           'requested_radius_m': 23.75, 'requested_island_side': 'left' if sign == 1 else 'right',
           'required_atoms': ['rel.occupies', 'kin.heading', 'kin.position'],
           'assignment_sha256': sha(folder / 'assignment-source.json'),
           'road_sha256': sha(road), 'island_geometry_sha256': sha(island),
           'tracks_sha256': sha(folder / 'requested-tracks.jsonl'),
           'original_native_observed': False, 'physical_island_verified': False,
           'legal_verdict_claimed': False}
    write(folder / 'config.json', cfg)
    return {'case_id': case_id, 'requested_frames': 600,
            'assignment_sha256': cfg['assignment_sha256'],
            'tracks_sha256': cfg['tracks_sha256']}


if __name__ == '__main__':
    print(json.dumps([build(case) for case in CASES]))
