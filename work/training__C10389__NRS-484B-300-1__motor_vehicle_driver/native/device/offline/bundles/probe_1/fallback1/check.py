"""Exact copied-source CPU check of C10389 stop-device requests."""
import argparse
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET

from build import (DEVICE_X, EXACT_LAW_TEXT_SHA, FROZEN_ASSIGNMENT_SHA,
                   FRAMES, POLICIES, RATE, SUFFIXES, request, road)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines()]


def check(bundle):
    bundle = Path(bundle)
    cfg = json.loads((bundle / 'config.json').read_text())
    a = json.loads((bundle / 'assignment-source.json').read_text())
    plan = json.loads((bundle / 'case-plan.json').read_text())
    suffix = cfg['case_id'].split('__')[-1]
    candidate = cfg['candidate_id']
    law = a['law_record']['text']
    if (suffix not in SUFFIXES or candidate not in POLICIES or
            sha(bundle / 'assignment-source.json') != FROZEN_ASSIGNMENT_SHA or
            hashlib.sha256(law.encode()).hexdigest() != EXACT_LAW_TEXT_SHA or
            cfg['case_id'] != cfg['assignment_id'] + '__' + suffix or
            cfg['assignment_id'] != a['assignment_id'] or
            cfg['source_text'] != law or plan['source_law']['text'] != law or
            a['cell']['layout'] != 'alley' or
            a['cell']['control'] != 'traffic_control_device' or
            a['actor'] != 'motor_vehicle_driver' or
            'official traffic-control device' not in law or
            'police officer' not in law or 'NRS 484B.307' not in law):
        raise ValueError('exact law, actor and cell source')
    for key, name in (('assignment_sha256', 'assignment-source.json'),
                      ('case_plan_sha256', 'case-plan.json'),
                      ('road_sha256', 'alley-stop.xodr'),
                      ('tracks_sha256', 'requested-tracks.jsonl')):
        if cfg[key] != sha(bundle / name):
            raise ValueError('copied source hash ' + name)
    if (bundle / 'alley-stop.xodr').read_text() != road():
        raise ValueError('altered source-bound road')
    root = ET.parse(bundle / 'alley-stop.xodr').getroot()
    signal = root.find('./road/signals/signal')
    lanes = root.findall('./road/lanes/laneSection/right/lane')
    if (root.find('./road').get('id') != '389' or
            [(lane.get('id'), lane.get('type')) for lane in lanes] != [('-1', 'driving')] or
            signal is None or signal.attrib != {'id': '3891',
                'name': 'C10389_authored_stop_control', 's': '50', 't': '-4.2',
                'zOffset': '0', 'hOffset': '0', 'pitch': '0', 'roll': '0',
                'dynamic': 'no', 'orientation': '+', 'country': 'US',
                'type': '206', 'subtype': '0', 'value': '0',
                'height': '0.75', 'width': '0.75'}):
        raise ValueError('authored Native stop-device topology')
    speed, camera, policy = POLICIES[candidate]
    obey = suffix == 'probe_1'
    if (cfg['requested_obey'] is not obey or
            cfg['requested_speed_mps'] != speed or cfg['camera_policy'] != camera or
            cfg['route_policy'] != policy or cfg['rate_hz'] != RATE or
            cfg['frames'] != FRAMES or cfg['device_id'] != '3891' or
            cfg['device_s_m'] != DEVICE_X or
            cfg['stop_hold_s'] != (1.0 if obey and policy == 'target' else 0.0) or
            cfg['official_placement_verified'] is not False or
            cfg['police_direction_verified'] is not False or
            cfg['original_native_observed'] is not False or
            cfg['status'] != 'unselected_native_request'):
        raise ValueError('candidate policy or unverified status')
    observed = rows(bundle / 'requested-tracks.jsonl')
    expected = request(speed, obey, policy)
    if observed != expected:
        raise ValueError('240 source-bound request rows')
    stopped = sum(row['requested_speed_mps'] == 0 for row in observed)
    requested_crossing = any(row['requested_ego_x_m'] > DEVICE_X for row in observed)
    if ((policy == 'stop_before_device' and (not stopped or requested_crossing)) or
            (policy == 'target' and not requested_crossing) or
            (obey and policy == 'target' and stopped != RATE) or
            (not obey and policy == 'target' and stopped)):
        raise ValueError('stop/crossing request semantics')
    return {'case_id': cfg['case_id'], 'candidate_id': candidate,
            'requested_obey': obey, 'requested_stopped_frames': stopped,
            'requested_crossing': requested_crossing,
            'observed_device_obedience': None,
            'official_placement_verified': False,
            'delivery_ready': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--bundle', type=Path, default=Path.cwd())
    args = parser.parse_args()
    print(json.dumps(check(args.bundle)))
