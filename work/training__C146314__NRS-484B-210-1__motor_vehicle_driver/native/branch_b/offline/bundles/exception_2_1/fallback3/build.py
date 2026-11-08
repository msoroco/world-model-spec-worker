"""Author paragraph (b) four-lane, parked-vehicle controlled Native requests."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
CASE = HERE.parent.parent
ROOT = CASE.parents[1]
POLICIES = {
    'primary': (8.0, 'standard', None),
    'fallback1': (7.0, 'standard', None),
    'fallback2': (8.0, 'elevated_overview', None),
    'fallback3': (8.0, 'standard', 45.0),
}
SOURCE = 'Upon a highway with unobstructed pavement which is not occupied by parked vehicles and which is of sufficient width for two or more lines of moving vehicles in each direction.'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def put(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')


def put_rows(path, values):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(''.join(json.dumps(row, sort_keys=True, allow_nan=False) + '\n'
                            for row in values))


def road():
    lane = lambda ident, mark: (f'<lane id="{ident}" type="driving" level="false">'
        '<width sOffset="0" a="3.5" b="0" c="0" d="0"/>'
        f'<roadMark sOffset="0" type="{mark}" color="white" width="0.12"/></lane>')
    return ('<?xml version="1.0" encoding="UTF-8"?>\n'
        '<OpenDRIVE><header revMajor="1" revMinor="4" '
        'name="C146314 paragraph b four moving lines" version="1.00" '
        'date="2026-11-08" north="8" south="-8" east="300" west="0" vendor="worker"/>'
        '<road name="four-lane authored pavement" length="300" id="211" junction="-1">'
        '<type s="0" type="town"><speed max="35" unit="mph"/></type>'
        '<planView><geometry s="0" x="0" y="0" hdg="0" length="300"><line/></geometry></planView>'
        '<lanes><laneSection s="0"><left>'+lane(1,'broken')+lane(2,'solid')+'</left>'
        '<center><lane id="0" type="none" level="false"><roadMark sOffset="0" '
        'type="solid" color="yellow" width="0.15"/></lane></center>'
        '<right>'+lane(-1,'broken')+lane(-2,'solid')+'</right></laneSection></lanes>'
        '<objects/><signals/></road></OpenDRIVE>\n')


def build():
    plan = json.loads((CASE/'case-plan.json').read_text())
    assignment = ROOT/'inputs'/CASE.name/'assignment.json'
    assert SOURCE in plan['source_law']['text']
    (HERE/'four-lane-pass.xodr').write_text(road())
    entries = []
    for witness, parked in (('exception_2_1', True), ('exception_2_2', False)):
        for candidate, (speed, camera, stop) in POLICIES.items():
            target = HERE/'drafts'/witness/candidate
            case_id = CASE.name+'__'+witness
            rows = []
            for i in range(240):
                t = (i+1)/20
                x = min(stop or 300, 5+speed*t)
                blend = max(0, min(1, (x-15)/20, (105-x)/20))
                y = -1.75-3.5*blend
                rows.append({
                    'frame': i, 'time_s': t,
                    'source_kind': 'authored_native_request',
                    'source_branch': 'NRS 484B.210(1)(b)',
                    'case_id': case_id, 'candidate_id': candidate,
                    'road_id': 211, 'ego_x_m': round(x,6), 'ego_y_m': round(y,6),
                    'ego_lane_id': -2 if y < -3.5 else -1,
                    'lead_x_m': round(35+4*t,6), 'lead_y_m': -1.75,
                    'lead_lane_id': -1,
                    'parked_vehicle_requested': parked,
                    'parked_x_m': 55 if parked else None,
                    'parked_y_m': -6.8 if parked else None,
                    'parked_lane_id': -2 if parked else None,
                    'four_driving_lanes_verified': False,
                    'parked_vehicle_observed': False,
                    'pavement_unobstructed_verified': False,
                    'actual_right_pass_observed': False,
                    'legal_verdict': None,
                })
            track = target/'requested-tracks.jsonl'
            put_rows(track, rows)
            cfg = {'format':'c146314-paragraph-b-request-v1',
                'assignment_id': CASE.name, 'case_id':case_id,
                'candidate_id':candidate, 'source_branch':'NRS 484B.210(1)(b)',
                'assignment_sha256':sha(assignment),
                'case_plan_sha256':sha(CASE/'case-plan.json'),
                'road_sha256':sha(HERE/'four-lane-pass.xodr'),
                'tracks_sha256':sha(track), 'rate_hz':20, 'frames':240,
                'requested_ego_speed_mps':speed, 'camera_policy':camera,
                'stop_x_m':stop, 'parked_vehicle_requested':parked,
                'four_driving_lanes_verified':False,
                'parked_vehicle_observed':False,
                'pavement_unobstructed_verified':False,
                'actual_right_pass_observed':False,
                'original_native_observed':False,
                'status':'unselected_native_request'}
            put(target/'config.json',cfg)
            entries.append({'case_id':case_id,'candidate_id':candidate,
                'config_sha256':sha(target/'config.json'),
                'tracks_sha256':sha(track),'status':'unselected_native_request'})
    manifest={'format':'c146314-paragraph-b-construction-v1',
        'assignment_id':CASE.name,'assignment_sha256':sha(assignment),
        'case_plan_sha256':sha(CASE/'case-plan.json'),
        'road_sha256':sha(HERE/'four-lane-pass.xodr'),
        'capture_sha256':sha(HERE/'capture.py'),
        'measurement_contract_sha256':sha(HERE/'measurement-contract.json'),
        'entries':entries,'original_native_observed':False,'delivery_ready':False}
    put(HERE/'manifest.json',manifest)
    return manifest


if __name__ == '__main__':
    print(json.dumps({'requests':len(build()['entries'])}))
