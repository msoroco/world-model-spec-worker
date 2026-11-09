"""Author unselected C10389 Native stop-device requests from frozen sources."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
CASE = HERE.parent.parent
ROOT = CASE.parents[1]
POLICIES = {
    'primary': (8.0, 'standard', 'target'),
    'fallback1': (5.0, 'standard', 'target'),
    'fallback2': (8.0, 'elevated_overview', 'target'),
    'fallback3': (8.0, 'standard', 'stop_before_device'),
}
SUFFIXES = ('probe_1', 'probe_2')
STOP_X = 44.0
DEVICE_X = 50.0
FRAMES = 240
RATE = 20


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')


def road():
    return '''<?xml version="1.0" encoding="UTF-8"?>
<OpenDRIVE><header revMajor="1" revMinor="4" name="C10389 alley device request" version="1.00" date="2026-11-08" north="4" south="-4" east="120" west="0" vendor="worker"/>
<road name="alley stop-device request" length="120" id="389" junction="-1">
<type s="0" type="town"><speed max="20" unit="mph"/></type>
<planView><geometry s="0" x="0" y="0" hdg="0" length="120"><line/></geometry></planView>
<lanes><laneSection s="0"><center><lane id="0" type="none" level="false"><roadMark sOffset="0" type="solid" color="yellow" width="0.15"/></lane></center><right><lane id="-1" type="driving" level="false"><width sOffset="0" a="3.5" b="0" c="0" d="0"/><roadMark sOffset="0" type="solid" color="white" width="0.12"/></lane></right></laneSection></lanes>
<objects/><signals><signal id="3891" name="C10389_authored_stop_control" s="50" t="-4.2" zOffset="0" hOffset="0" pitch="0" roll="0" dynamic="no" orientation="+" country="US" type="206" subtype="0" value="0" height="0.75" width="0.75"/></signals>
</road></OpenDRIVE>
'''


def request(speed, obey, policy):
    rows = []
    for frame in range(FRAMES):
        t = (frame + 1) / RATE
        reach = (STOP_X - 5.0) / speed
        if policy == 'stop_before_device':
            x = min(STOP_X, 5.0 + speed * t)
            target_speed = 0.0 if t >= reach else speed
        elif obey and reach <= t < reach + 1.0:
            x = STOP_X
            target_speed = 0.0
        elif obey and t >= reach + 1.0:
            x = STOP_X + speed * (t - reach - 1.0)
            target_speed = speed
        else:
            x = 5.0 + speed * t
            target_speed = speed
        rows.append({'frame': frame, 'time_s': t,
                     'requested_ego_x_m': round(x, 6),
                     'requested_ego_y_m': -1.75,
                     'requested_speed_mps': target_speed,
                     'requested_road_id': 389, 'requested_lane_id': -1,
                     'requested_stop_line_x_m': DEVICE_X,
                     'requested_stop_hold': obey,
                     'official_placement_verified': False,
                     'police_direction_verified': False,
                     'signal_specific_exception_reviewed': False,
                     'observed_device_obedience': None,
                     'legal_verdict': None})
    return rows


def build():
    assignment = ROOT / 'inputs' / CASE.name / 'assignment.json'
    a = json.loads(assignment.read_text())
    plan_path = CASE / 'case-plan.json'
    plan = json.loads(plan_path.read_text())
    law = a['law_record']['text']
    if (plan['source_law']['text'] != law or
            a['cell']['layout'] != 'alley' or
            a['cell']['control'] != 'traffic_control_device' or
            a['actor'] != 'motor_vehicle_driver' or
            'official traffic-control device' not in law or
            'police officer' not in law or
            'NRS 484B.307' not in law):
        raise ValueError('frozen law or cell changed')
    road_path = HERE / 'alley-stop.xodr'
    road_path.write_text(road())
    entries = []
    for suffix in SUFFIXES:
        obey = suffix == 'probe_1'
        for candidate, (speed, camera, policy) in POLICIES.items():
            target = HERE / 'drafts' / suffix / candidate
            rows = request(speed, obey, policy)
            tracks = target / 'requested-tracks.jsonl'
            tracks.parent.mkdir(parents=True, exist_ok=True)
            tracks.write_text(''.join(json.dumps(row, sort_keys=True) + '\n' for row in rows))
            cfg = {'format': 'c10389-device-native-request-v1',
                   'assignment_id': CASE.name,
                   'case_id': CASE.name + '__' + suffix,
                   'candidate_id': candidate,
                   'source_text': law,
                   'assignment_sha256': sha(assignment),
                   'case_plan_sha256': sha(plan_path),
                   'road_sha256': sha(road_path),
                   'tracks_sha256': sha(tracks),
                   'rate_hz': RATE, 'frames': FRAMES,
                   'requested_obey': obey, 'requested_speed_mps': speed,
                   'camera_policy': camera, 'route_policy': policy,
                   'device_id': '3891', 'device_s_m': DEVICE_X,
                   'stop_hold_s': 1.0 if obey and policy == 'target' else 0.0,
                   'official_placement_verified': False,
                   'police_direction_verified': False,
                   'original_native_observed': False,
                   'status': 'unselected_native_request'}
            write_json(target / 'config.json', cfg)
            entries.append({'case_id': cfg['case_id'], 'candidate_id': candidate,
                            'config_sha256': sha(target / 'config.json'),
                            'tracks_sha256': sha(tracks),
                            'status': 'unselected_native_request'})
    manifest = {'format': 'c10389-device-native-construction-v1',
                'assignment_id': CASE.name,
                'assignment_sha256': sha(assignment),
                'case_plan_sha256': sha(plan_path),
                'road_sha256': sha(road_path),
                'capture_sha256': sha(HERE / 'capture.py'),
                'measurement_contract_sha256': sha(HERE / 'measurement-contract.json'),
                'saved_sha256': sha(HERE / 'saved.py'),
                'fixture_raw_sha256': sha(HERE / 'fixture_raw.py'),
                'route_fallbacks_sha256': sha(HERE / 'route_fallbacks.py'),
                'entries': entries,
                'original_native_observed': False,
                'delivery_ready': False}
    write_json(HERE / 'manifest.json', manifest)
    return manifest


if __name__ == '__main__':
    print(json.dumps({'requests': len(build()['entries'])}))
