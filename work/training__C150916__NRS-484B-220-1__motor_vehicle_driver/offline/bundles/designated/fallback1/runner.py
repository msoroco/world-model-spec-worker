"""CPU exact-bundle check for a C150916 Native request.

CARLA execution and physical sign observation are separate pending work.
"""
import argparse
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check(bundle):
    bundle = Path(bundle)
    config = json.loads((bundle/'config.json').read_text())
    assignment = json.loads((bundle/'assignment-source.json').read_text())
    plan = json.loads((bundle/'case-plan.json').read_text())
    if (config['format'] != 'c150916-native-request-v1' or
            assignment['assignment_id'] != config['assignment_id'] or
            plan['assignment_id'] != config['assignment_id'] or
            config['assignment_sha256'] != sha(bundle/'assignment-source.json') or
            config['case_plan_sha256'] != sha(bundle/'case-plan.json') or
            config['road_sha256'] != sha(bundle/'road.xodr') or
            config['tracks_sha256'] != sha(bundle/'requested-tracks.jsonl') or
            config['status'] != 'unselected_native_request'):
        raise ValueError('Exact one-way bundle source binding differs')
    case = config['requested_direction']
    candidate = config['candidate_id']
    if (case not in ('designated','opposite') or
            candidate not in ('primary','fallback1','fallback2','fallback3') or
            config['case_id'] != config['assignment_id']+'__'+case or
            config['case_id'] not in {row['case_id'] for row in plan['cases']}):
        raise ValueError('One-way case or candidate differs')
    road = ET.parse(bundle/'road.xodr').getroot()
    lanes = {int(l.attrib['id']): l.attrib['type'] for l in road.findall('.//lane')}
    signs = {int(s.attrib['id']): s for s in road.findall('.//signal')}
    if lanes != {-2:'driving',-1:'driving',0:'none'} or set(signs) != {101,102} or any(
            s.attrib['type'] != 'R6-1' or s.attrib['orientation'] != '+' for s in signs.values()):
        raise ValueError('One-way road or sign request differs')
    rows = [json.loads(line) for line in (bundle/'requested-tracks.jsonl').read_text().splitlines()]
    if len(rows) != 240 or config['rate_hz'] != 20 or config['frames'] != 240:
        raise ValueError('One-way requested frame count differs')
    direction = 1 if case == 'designated' else -1
    start = -20 if case == 'designated' else 220
    lane = -2 if candidate == 'fallback2' else -1
    speed = 4 if candidate == 'fallback1' else 3 if candidate == 'fallback3' else 8
    for i, row in enumerate(rows):
        t = (i+1)/20
        displacement = min(12,speed*t) if candidate == 'fallback3' else speed*t
        if (row['frame'] != i or abs(row['time_s']-t) > 1e-6 or
                abs(row['ego_x_m']-(start+direction*displacement)) > 1e-4 or
                row['ego_y_m'] != (-5.25 if lane == -2 else -1.75) or
                row['ego_heading_deg'] != (0 if direction == 1 else 180) or
                row['lane_id'] != lane or row['requested_direction'] != case):
            raise ValueError('One-way request trajectory differs')
    return {'format':'c150916-copied-runner-cpu-check-v1',
            'case_id':config['case_id'],'candidate_id':candidate,
            'requested_frames':len(rows),'road_sign_requests':sorted(signs),
            'carla_imported':False,'physical_sign_verified':False,
            'designation_authority_verified':False,'delivery_ready':False}


if __name__ == '__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--check',action='store_true',required=True)
    parser.add_argument('--bundle',type=Path,required=True)
    args=parser.parse_args()
    print(json.dumps(check(args.bundle)))
