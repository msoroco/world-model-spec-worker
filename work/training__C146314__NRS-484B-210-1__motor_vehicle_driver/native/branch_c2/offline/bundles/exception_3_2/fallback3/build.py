"""Author separate paragraph (c)(2) private-way crossing requests."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
CASE = HERE.parent.parent
ROOT = CASE.parents[1]
SOURCE = 'does not travel through an intersection or past any private way that is used to enter or exit the highway'
POLICIES = {'primary': (8.0, 'standard', None),
            'fallback1': (7.5, 'standard', None),
            'fallback2': (8.0, 'elevated_overview', None),
            'fallback3': (8.0, 'standard', 35.0)}
PRIVATE_WAY_X = 50.0
START_X = 10.0
EXIT_X = 75.0


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def put(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, allow_nan=False)+'\n')


def put_rows(path, values):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(''.join(json.dumps(v, sort_keys=True, allow_nan=False)+'\n'
                            for v in values))


def road(private_way):
    main = '''<road name="main highway with unmarked shoulder" length="300" id="212" junction="-1">
<type s="0" type="town"><speed max="35" unit="mph"/></type>
<planView><geometry s="0" x="0" y="0" hdg="0" length="300"><line/></geometry></planView>
<lanes><laneSection s="0"><center><lane id="0" type="none" level="false"><roadMark sOffset="0" type="solid" color="yellow" width="0.15"/></lane></center>
<right><lane id="-1" type="driving" level="false"><width sOffset="0" a="3.5" b="0" c="0" d="0"/><roadMark sOffset="0" type="solid" color="white" width="0.12"/></lane>
<lane id="-2" type="shoulder" level="false"><width sOffset="0" a="3.5" b="0" c="0" d="0"/><roadMark sOffset="0" type="none" color="white" width="0"/></lane></right></laneSection></lanes><objects/><signals/></road>'''
    spur = '''<road name="private access way entering highway" length="20" id="214" junction="-1">
<link><predecessor elementType="junction" elementId="1"/></link>
<type s="0" type="town"><speed max="10" unit="mph"/></type>
<planView><geometry s="0" x="50" y="-3.5" hdg="-1.5707963267948966" length="20"><line/></geometry></planView>
<lanes><laneSection s="0"><center><lane id="0" type="none" level="false"><roadMark sOffset="0" type="none" color="white" width="0"/></lane></center>
<right><lane id="-1" type="driving" level="false"><link><predecessor id="-1"/></link><width sOffset="0" a="3.5" b="0" c="0" d="0"/><roadMark sOffset="0" type="none" color="white" width="0"/></lane></right></laneSection></lanes><objects/><signals/></road>
<junction name="private way connection" id="1"><connection id="0" incomingRoad="212" connectingRoad="214" contactPoint="start"><laneLink from="-1" to="-1"/></connection></junction>'''
    return ('<?xml version="1.0" encoding="UTF-8"?>\n'
            '<OpenDRIVE><header revMajor="1" revMinor="4" name="C146314 paragraph c2 private way" version="1.00" date="2026-11-08" north="3.5" south="-24" east="300" west="0" vendor="worker"/>\n'
            + main + ('\n'+spur if private_way else '') + '</OpenDRIVE>\n')


def build():
    plan = json.loads((CASE/'case-plan.json').read_text())
    if SOURCE not in plan['source_law']['text']:
        raise ValueError('paragraph (c)(2) frozen source differs')
    assignment = ROOT/'inputs'/CASE.name/'assignment.json'
    entries = []
    roads = {}
    for witness, private_way in (('exception_3_1', True), ('exception_3_2', False)):
        road_path = HERE/'roads'/(witness+'.xodr')
        road_path.parent.mkdir(parents=True, exist_ok=True)
        road_path.write_text(road(private_way))
        roads[witness] = sha(road_path)
        for candidate, (speed, camera, stop) in POLICIES.items():
            target = HERE/'drafts'/witness/candidate
            case_id = CASE.name+'__'+witness
            values = []
            for i in range(240):
                t = (i+1)/20
                x = min(stop or 300, 5+speed*t)
                blend = max(0, min(1, (x-(START_X-3.8))/5,
                                   (EXIT_X+3.8-x)/5))
                values.append({'frame': i, 'time_s': t,
                    'source_kind': 'authored_native_request',
                    'source_branch': 'NRS 484B.210(1)(c)(2)',
                    'case_id': case_id, 'candidate_id': candidate,
                    'road_id': 212, 'ego_x_m': round(x, 6),
                    'ego_y_m': round(-1.75-3.5*blend, 6),
                    'lead_x_m': round(30+4*t, 6), 'lead_y_m': -1.75,
                    'unmarked_segment_start_x_m': START_X,
                    'unmarked_segment_end_x_m': EXIT_X,
                    'private_way_x_m': PRIVATE_WAY_X,
                    'private_way_requested': private_way,
                    'requested_c2_no_private_way_passed': not private_way,
                    'requested_c1_over_200ft': EXIT_X-START_X > 60.96,
                    'actual_private_way_passed_observed': False,
                    'actual_unmarked_distance_observed': False,
                    'actual_right_pass_observed': False,
                    'pavement_unobstructed_verified': False,
                    'no_parked_vehicles_verified': False,
                    'legal_verdict': None})
            track = target/'requested-tracks.jsonl'
            put_rows(track, values)
            cfg = {'format': 'c146314-paragraph-c2-request-v1',
                'assignment_id': CASE.name, 'case_id': case_id,
                'candidate_id': candidate,
                'source_branch': 'NRS 484B.210(1)(c)(2)',
                'assignment_sha256': sha(assignment),
                'case_plan_sha256': sha(CASE/'case-plan.json'),
                'road_sha256': sha(road_path),
                'tracks_sha256': sha(track),
                'rate_hz': 20, 'frames': 240,
                'requested_ego_speed_mps': speed,
                'camera_policy': camera, 'stop_x_m': stop,
                'unmarked_segment_start_x_m': START_X,
                'unmarked_segment_end_x_m': EXIT_X,
                'private_way_x_m': PRIVATE_WAY_X,
                'private_way_requested': private_way,
                'requested_c2_no_private_way_passed': not private_way,
                'requested_c1_over_200ft': True,
                'actual_private_way_passed_observed': False,
                'actual_unmarked_distance_observed': False,
                'actual_right_pass_observed': False,
                'original_native_observed': False,
                'status': 'unselected_native_request'}
            put(target/'config.json', cfg)
            entries.append({'case_id': case_id, 'candidate_id': candidate,
                'config_sha256': sha(target/'config.json'),
                'tracks_sha256': sha(track),
                'road_sha256': sha(road_path),
                'status': 'unselected_native_request'})
    manifest = {'format': 'c146314-paragraph-c2-construction-v1',
        'assignment_id': CASE.name, 'assignment_sha256': sha(assignment),
        'case_plan_sha256': sha(CASE/'case-plan.json'),
        'road_sha256_by_witness': roads,
        'capture_sha256': sha(HERE/'capture.py'),
        'measurement_contract_sha256': sha(HERE/'measurement-contract.json'),
        'entries': entries, 'original_native_observed': False,
        'delivery_ready': False}
    put(HERE/'manifest.json', manifest)
    return manifest


if __name__ == '__main__':
    print(json.dumps({'requests': len(build()['entries'])}))
