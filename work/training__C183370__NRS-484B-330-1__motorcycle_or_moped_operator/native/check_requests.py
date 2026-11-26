"""Check exact flagger constructions without importing or starting CARLA."""

import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET


HERE = Path(__file__).resolve().parent
ASSIGNMENT = HERE.parent.name


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read_case(suffix, repo=Path('.'), base=HERE):
    if suffix not in ('probe_a', 'probe_b'):
        raise ValueError('Unknown exact flagger case')
    folder = Path(base) / suffix
    config = json.loads((folder / 'config.json').read_text())
    expected_policy = 'hold_until_release' if suffix == 'probe_a' else 'cross_during_stop'
    if (config['assignment_id'] != ASSIGNMENT or
            config['case_id'] != ASSIGNMENT + '__' + suffix or
            config['candidate_id'] != 'primary' or
            config['law_id'] != 'NRS-484B-330-1' or
            config['cell_id'] != 'C183370' or
            config['actor'] != 'motorcycle_or_moped_operator' or
            config['rate_hz'] != 20 or config['duration_s'] != 30 or
            config['frame_count'] != 600 or
            config['controller_policy'] != expected_policy or
            config['stop_line_x_m'] != 0 or
            config['requested_route'] != 'driving_lane_beside_paved_shoulder' or
            config['physical_or_legal_outcome_claimed'] is not False):
        raise ValueError('Exact flagger config differs')
    if (set(config['cameras']) != {'overview', 'approach', 'flagger', 'rear'} or
            config['cameras']['overview']['width'] != 1920 or
            any(v['width'] != 1280 for k, v in config['cameras'].items()
                if k != 'overview')):
        raise ValueError('Four-camera plan differs')
    source = Path(repo).resolve() / config['assignment_source']
    if sha(source) != config['assignment_sha256']:
        raise ValueError('Frozen assignment source differs')
    assignment = json.loads(source.read_text())
    if (assignment['assignment_id'] != ASSIGNMENT or
            assignment['cell']['layout'] != 'paved_shoulder' or
            assignment['cell']['maneuver'] != 'travel' or
            assignment['cell']['control'] != 'flagger'):
        raise ValueError('Frozen flagger cell differs')
    road = folder / 'road.xodr'
    tracks = folder / 'requested-tracks.jsonl'
    if sha(road) != config['road_sha256'] or sha(tracks) != config['tracks_sha256']:
        raise ValueError('Authored construction source differs')
    root = ET.parse(road).getroot()
    if root.tag != 'OpenDRIVE':
        raise ValueError('OpenDRIVE root missing')
    lanes = {int(l.attrib['id']): l.attrib['type'] for l in root.findall('.//lane')}
    if lanes.get(-1) != 'driving' or lanes.get(-2) != 'shoulder':
        raise ValueError('Separate driving lane and paved shoulder absent')
    rows = [json.loads(line) for line in tracks.read_text().splitlines()]
    if len(rows) != 600:
        raise ValueError('Thirty-second construction absent')
    for index, row in enumerate(rows):
        if (row['frame'] != 1000 + index or
                abs(row['time_s'] - index / 20) > 1e-9 or
                row['requested_center_y_m'] != -1.75 or
                row['flagger_target_x_m'] != 0 or
                row['flagger_target_y_m'] != -7 or
                row['motorcycle_blueprint'] != 'vehicle.kawasaki.ninja' or
                row['source_kind'] != 'authored_native_request' or
                row['signal'] != ('stop' if 100 <= index < 300 else 'release')):
            raise ValueError('Frame, actor, geometry or signal request differs')
    crossing = next((r['frame'] for r in rows if r['requested_center_x_m'] >= 0), None)
    if crossing != (1350 if suffix == 'probe_a' else 1200):
        raise ValueError('Controlled stop-line crossing differs')
    if not all(r['requested_center_x_m'] <= 0 for r in rows[:100]):
        raise ValueError('Subject begins past stop line')
    return config, rows


def check_pair(repo=Path('.'), base=HERE):
    first, a = read_case('probe_a', repo, base)
    second, b = read_case('probe_b', repo, base)
    fixed = ('assignment_id', 'law_id', 'cell_id', 'actor', 'rate_hz',
             'duration_s', 'frame_count', 'stop_line_x_m', 'requested_route',
             'signal_policy', 'cameras', 'assignment_source', 'assignment_sha256',
             'road_sha256', 'source_review_required')
    if any(first[key] != second[key] for key in fixed):
        raise ValueError('Comparison fixed construction differs')
    if any(a[i]['signal'] != b[i]['signal'] or
           a[i]['requested_center_y_m'] != b[i]['requested_center_y_m']
           for i in range(600)):
        raise ValueError('Comparison signal or route differs')
    return {'passed': True, 'cases': [first['case_id'], second['case_id']],
            'frames_per_case': 600, 'camera_count': 4,
            'crossing_frames': [1350, 1200], 'original_native_observed': False,
            'flagger_authority_or_visibility_verified': False}


if __name__ == '__main__':
    print(json.dumps(check_pair()))
