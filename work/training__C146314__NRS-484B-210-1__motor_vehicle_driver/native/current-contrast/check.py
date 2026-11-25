"""Validate a copied 600-frame paragraph (d) request without claiming motion."""
import hashlib
import json
import math
from pathlib import Path
import xml.etree.ElementTree as ET


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def check(bundle):
    bundle = Path(bundle)
    cfg = json.loads((bundle / 'config.json').read_text())
    assignment = json.loads((bundle / 'assignment-source.json').read_text())
    plan = json.loads((bundle / 'case-plan.json').read_text())
    required = {'road_sha256': 'one-way-pass.xodr',
        'tracks_sha256': 'requested-tracks.jsonl',
        'assignment_sha256': 'assignment-source.json',
        'case_plan_sha256': 'case-plan.json'}
    for key, filename in required.items():
        if cfg[key] != sha(bundle / filename):
            raise ValueError('Changed or missing source: ' + filename)
    if (cfg['assignment_id'] != assignment['assignment_id'] or
            cfg['assignment_id'] != plan['assignment_id'] or
            cfg['case_id'] != cfg['assignment_id'] + '__witness_2'):
        raise ValueError('Assignment identity differs')
    if cfg['assignment_id'] != plan['assignment_id']:
        raise ValueError('Plan identity differs')
    if not (cfg['frames'] == 600 and cfg['rate_hz'] == 20 and
            cfg['duration_s'] == 30 and
            cfg['camera_names'] == ['overview', 'approach', 'reference_corner', 'driver_reference']):
        raise ValueError('Current duration or camera contract differs')
    if not (cfg['law_id'] == 'NRS-484B-210-1' and cfg['cell_id'] == 'C146314'
            and cfg['actor'] == 'motor_vehicle_driver' and
            cfg['original_native_observed'] is False and
            cfg['delivery_ready'] is False):
        raise ValueError('Case identity or diagnostic status differs')
    if 'Upon any highway on which traffic is restricted to one direction' not in assignment['law']['text']:
        raise ValueError('Frozen paragraph (d) differs')
    road = ET.parse(bundle / 'one-way-pass.xodr').getroot().find('road')
    widths = [float(lane.find('width').get('a')) for lane in road.findall('./lanes/laneSection/right/lane')]
    if road.get('id') != '210' or widths != [3.5, 3.5]:
        raise ValueError('Authored one-way geometry differs')
    lines = (bundle / 'requested-tracks.jsonl').read_text().splitlines()
    if len(lines) != 600:
        raise ValueError('Requested frame count differs')
    for i, line in enumerate(lines):
        row = json.loads(line)
        t = (i + 1) / 20
        x = 5 + 8 * t
        blend = max(0, min(1, (x - 15) / 20, (105 - x) / 20))
        y = -1.75 - 3.5 * blend
        if not (row['frame'] == i and row['time_s'] == t and
                row['source_kind'] == 'authored_native_request' and
                row['case_id'] == cfg['case_id'] and row['candidate_id'] == 'primary' and
                math.isclose(row['ego_x_m'], x, abs_tol=1e-6) and
                math.isclose(row['ego_y_m'], y, abs_tol=1e-6) and
                row['ego_lane_id'] == (-2 if y < -3.5 else -1) and
                row['actual_right_pass_observed'] is False and
                row['one_way_designation_verified'] is False and
                row['unobstructed_pavement_verified'] is False and
                row['legal_verdict'] is None):
            raise ValueError('Requested frame differs: ' + str(i))
    if not (cfg.get('right_lane_obstruction_requested') is True and
            cfg.get('obstruction_x_m') == 55.0 and
            cfg.get('obstruction_y_m') == -6.8 and
            all(json.loads(line).get('right_lane_obstruction_requested') is True and
                json.loads(line).get('obstruction_x_m') == 55.0 and
                json.loads(line).get('obstruction_y_m') == -6.8 and
                json.loads(line).get('obstruction_significance_verified') is False
                for line in lines)):
        raise ValueError('Requested obstruction differs')
    return {'case_id': cfg['case_id'], 'candidate_id': 'primary',
            'frames': 600, 'cameras': 4,
            'source_bound': True, 'original_native_observed': False,
            'delivery_ready': False}


if __name__ == '__main__':
    print(json.dumps(check(Path.cwd())))
