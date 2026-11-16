"""Author exact right-pass clearance requests; no legal safety finding is made."""
import hashlib
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[1]
NATIVE = ROOT/'native'
POLICIES = {
    'primary': {'ego_speed_mps': 8.0, 'lead_speed_mps': 4.0,
                'lane_change_end_x_m': 31, 'camera_policy': 'standard'},
    'fallback1': {'ego_speed_mps': 7.5, 'lead_speed_mps': 3.5,
                  'lane_change_end_x_m': 31, 'camera_policy': 'standard'},
    'fallback2': {'ego_speed_mps': 8.0, 'lead_speed_mps': 4.0,
                  'lane_change_end_x_m': 31, 'camera_policy': 'elevated_overview'},
    'fallback3': {'ego_speed_mps': 8.0, 'lead_speed_mps': 4.0,
                  'lane_change_end_x_m': 39, 'camera_policy': 'standard'},
}
TARGET_Y = {'reference': -5.5, 'contrast': -4.8}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, allow_nan=False)+'\n')


def road():
    return '''<?xml version="1.0" encoding="UTF-8"?>
<OpenDRIVE><header revMajor="1" revMinor="4" name="C146314 right-pass safety request" version="1.00" date="2026-11-16" north="4" south="-8" east="300" west="0" vendor="worker"/>
<road name="one-way two-lane paved pass corridor" length="300" id="210" junction="-1">
<type s="0" type="town"><speed max="35" unit="mph"/></type>
<planView><geometry s="0" x="0" y="0" hdg="0" length="300"><line/></geometry></planView>
<lanes><laneSection s="0"><center><lane id="0" type="none" level="false"><roadMark sOffset="0" type="solid" color="yellow" width="0.15"/></lane></center>
<right><lane id="-1" type="driving" level="false"><width sOffset="0" a="3.5" b="0" c="0" d="0"/><roadMark sOffset="0" type="broken" color="white" width="0.12"/></lane>
<lane id="-2" type="driving" level="false"><width sOffset="0" a="3.5" b="0" c="0" d="0"/><roadMark sOffset="0" type="solid" color="white" width="0.12"/></lane></right></laneSection></lanes>
<objects/><signals/></road></OpenDRIVE>
'''


def smooth(value):
    value = max(0.0, min(1.0, value))
    return value*value*(3-2*value)


def requested_track(witness, candidate, policy):
    """The paired witness changes only the right-lane lateral apex."""
    rows = []
    for i in range(240):
        time_s = (i+1)/20
        ego_x = 5+policy['ego_speed_mps']*time_s
        lead_x = 35+policy['lead_speed_mps']*time_s
        entering = smooth((ego_x-11)/(policy['lane_change_end_x_m']-11))
        returning = smooth((ego_x-91)/18)
        y = -1.75+(TARGET_Y[witness]+1.75)*entering*(1-returning)
        phase = ('approach' if entering == 0 else 'right_entry' if entering < 1
                 else 'passing_right' if returning == 0 else 'return')
        rows.append({'frame': i, 'time_s': time_s, 'source_kind': 'authored_native_request',
            'case_id': ROOT.name+'__'+witness, 'candidate_id': candidate,
            'road_id': 210, 'phase': phase,
            'ego_x_m': round(ego_x, 6), 'ego_y_m': round(y, 6),
            'ego_lane_id': -2 if y < -3.5 else -1,
            'ego_requested_speed_mps': policy['ego_speed_mps'],
            'lead_x_m': round(lead_x, 6), 'lead_y_m': -1.75,
            'lead_lane_id': -1, 'lead_requested_speed_mps': policy['lead_speed_mps'],
            'requested_lateral_apex_y_m': TARGET_Y[witness],
            'requested_nominal_body_gap_m': round(abs(TARGET_Y[witness]+1.75)-1.8, 6),
            'actual_pass_observed': False, 'actual_clearance_observed': False,
            'legal_safety_verdict': None})
    return rows


def build():
    NATIVE.mkdir(exist_ok=True)
    road_path = NATIVE/'right-pass-road.xodr'
    road_path.write_text(road())
    assignment = REPO/'inputs'/ROOT.name/'assignment.json'
    plan = ROOT/'case-plan.json'
    entries = []
    for witness in TARGET_Y:
        for candidate, policy in POLICIES.items():
            folder = NATIVE/'drafts'/witness/candidate
            folder.mkdir(parents=True, exist_ok=True)
            track = folder/'requested-tracks.jsonl'
            track.write_text(''.join(json.dumps(row, allow_nan=False)+'\n'
                                     for row in requested_track(witness, candidate, policy)))
            config = {'format': 'c146314-right-pass-clearance-request-v1',
                'assignment_id': ROOT.name, 'case_id': ROOT.name+'__'+witness,
                'candidate_id': candidate, 'law_id': 'NRS-484B-210-2',
                'cell_id': 'C146314', 'actor': 'motor_vehicle_driver',
                'road_sha256': sha(road_path), 'tracks_sha256': sha(track),
                'assignment_sha256': sha(assignment), 'case_plan_sha256': sha(plan),
                'rate_hz': 20, 'frames': 240, 'camera_policy': policy['camera_policy'],
                'ego_requested_speed_mps': policy['ego_speed_mps'],
                'lead_requested_speed_mps': policy['lead_speed_mps'],
                'lane_change_end_x_m': policy['lane_change_end_x_m'],
                'requested_lateral_apex_y_m': TARGET_Y[witness],
                'requested_nominal_body_gap_m': round(abs(TARGET_Y[witness]+1.75)-1.8, 6),
                'original_native_observed': False, 'legal_safety_verdict': None,
                'status': 'unselected_native_request'}
            write(folder/'config.json', config)
            entries.append({'case_id': config['case_id'], 'candidate_id': candidate,
                            'config_sha256': sha(folder/'config.json'),
                            'tracks_sha256': sha(track)})
    manifest = {'format': 'c146314-210-2-authored-requests-v1',
        'assignment_id': ROOT.name, 'road_sha256': sha(road_path),
        'assignment_sha256': sha(assignment), 'case_plan_sha256': sha(plan),
        'entries': entries, 'original_native_observed': False,
        'legal_safety_verdict': None, 'delivery_ready': False}
    write(NATIVE/'manifest.json', manifest)
    return manifest


if __name__ == '__main__':
    print(json.dumps({'requests': len(build()['entries'])}))
