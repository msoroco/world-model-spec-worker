"""Independent geometry, 1,920-frame and source audit of one-way requests."""
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET

HERE = Path(__file__).resolve().parent
CASE = HERE.parent
ROOT = CASE.parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audit():
    manifest_path = HERE/'drafts'/'manifest.json'
    manifest = json.loads(manifest_path.read_text())
    source = ROOT/'inputs'/CASE.name/'assignment.json'
    plan = CASE/'case-plan.json'
    road = HERE/'road.xodr'
    if (manifest['format'] != 'c150916-native-construction-manifest-v1' or
            manifest['assignment_id'] != CASE.name or
            manifest['assignment_sha256'] != sha(source) or
            manifest['case_plan_sha256'] != sha(plan) or
            manifest['road_sha256'] != sha(road) or
            manifest['original_native_observed'] or manifest['sign_authority_verified'] or
            manifest['delivery_ready'] or len(manifest['entries']) != 8):
        raise ValueError('One-way request provenance or status differs')
    doc = ET.parse(road).getroot()
    road_element = doc.find('road')
    if road_element is None or float(road_element.attrib['length']) != 400:
        raise ValueError('One-way road envelope differs')
    lanes = {int(node.attrib['id']): node.attrib['type'] for node in doc.findall('.//lane')}
    if lanes != {-2: 'driving', -1: 'driving', 0: 'none'}:
        raise ValueError('One-way lane topology differs')
    signals = {int(node.attrib['id']): node for node in doc.findall('.//signal')}
    if set(signals) != {101, 102} or any(node.attrib['type'] != 'R6-1' or
                                          node.attrib['orientation'] != '+' or
                                          node.find('validity').attrib != {'fromLane':'-2','toLane':'-1'}
                                          for node in signals.values()):
        raise ValueError('One-way sign request differs')
    if [float(signals[n].attrib['s']) for n in (101,102)] != [105,295]:
        raise ValueError('One-way sign stations differ')
    expected = {(case, candidate) for case in ('designated','opposite')
                for candidate in ('primary','fallback1','fallback2','fallback3')}
    seen = set()
    for entry in manifest['entries']:
        case = entry['case_id'].removeprefix(CASE.name+'__')
        candidate = entry['candidate_id']
        if (case, candidate) not in expected or (case, candidate) in seen:
            raise ValueError('One-way request case coverage differs')
        seen.add((case,candidate))
        folder = HERE/'drafts'/case/candidate
        config_path = folder/'config.json'
        track_path = folder/'requested-tracks.jsonl'
        config = json.loads(config_path.read_text())
        if (entry['config'] != str(config_path.relative_to(CASE)) or
                entry['config_sha256'] != sha(config_path) or
                entry['tracks_sha256'] != sha(track_path) or
                entry['status'] != 'unselected_native_request' or
                config['status'] != 'unselected_native_request' or
                config['assignment_sha256'] != sha(source) or
                config['case_plan_sha256'] != sha(plan) or
                config['road_sha256'] != sha(road) or
                config['tracks_sha256'] != sha(track_path)):
            raise ValueError('One-way request source binding differs')
        rows = [json.loads(line) for line in track_path.read_text().splitlines()]
        if len(rows) != 240 or config['frames'] != 240 or config['rate_hz'] != 20:
            raise ValueError('One-way request frame count differs')
        direction = 1 if case == 'designated' else -1
        start_x = -20 if case == 'designated' else 220
        lane = -2 if candidate == 'fallback2' else -1
        speed = {'primary':8,'fallback1':4,'fallback2':8,'fallback3':3}[candidate]
        policy = {'primary':'constant_speed_traverse','fallback1':'slow_sign_approach',
                  'fallback2':'outer_lane_traverse','fallback3':'stop_before_entry'}[candidate]
        if (config['case_id'] != CASE.name+'__'+case or config['candidate_id'] != candidate or
                config['requested_direction'] != case or config['lane_id'] != lane or
                config['policy'] != policy):
            raise ValueError('One-way candidate policy differs')
        for i, row in enumerate(rows):
            t = (i+1)/20
            distance = min(speed*t,12) if candidate == 'fallback3' else speed*t
            moving = speed if candidate != 'fallback3' or speed*t < 12 else 0
            if (row['frame'] != i or abs(row['time_s']-t) > 1e-6 or
                    abs(row['ego_x_m']-(start_x+direction*distance)) > 1e-4 or
                    row['ego_y_m'] != (-5.25 if lane == -2 else -1.75) or
                    row['ego_heading_deg'] != (0 if direction == 1 else 180) or
                    row['ego_speed_mps'] != moving or row['lane_id'] != lane or
                    row['requested_direction'] != case or row['source_kind'] != 'authored_request'):
                raise ValueError('One-way authored trajectory differs')
            if not -100 <= row['ego_x_m'] <= 300:
                raise ValueError('One-way request leaves road envelope')
        if candidate == 'fallback3' and not (rows[-1]['ego_x_m'] < 5 if direction == 1 else rows[-1]['ego_x_m'] > 195):
            raise ValueError('Stop request did not stop before sign')
    if seen != expected:
        raise ValueError('One-way candidate coverage incomplete')
    receipt = {'format':'c150916-independent-construction-audit-v1',
               'assignment_id': CASE.name, 'manifest_sha256': sha(manifest_path),
               'candidate_requests_checked': 8, 'requested_rows_checked': 1920,
               'physical_sign_verified': False, 'designation_authority_verified': False,
               'original_native_observed': False, 'delivery_ready': False}
    (HERE/'construction-audit.json').write_text(json.dumps(receipt, indent=2)+'\n')
    return receipt


if __name__ == '__main__':
    print(json.dumps(audit()))
