"""Author controlled C10374 safety-zone Native requests; no legal outcome."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
CASE = HERE.parent.parent
ROOT = CASE.parents[1]
LAW = 'No vehicle shall at any time be driven through or within a safety zone.'
POLICIES = {'primary': (8.0, 'standard', None),
            'fallback1': (5.0, 'standard', None),
            'fallback2': (8.0, 'elevated_overview', None),
            'fallback3': (8.0, 'standard', 35.0)}
CASES = ('selected_c5852cfd__condition_a', 'selected_c5852cfd__condition_b')
ZONE = (40.0, 60.0, -3.5, 0.0)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def put(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, allow_nan=False)+'\n')


def put_rows(path, values):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(''.join(json.dumps(row, sort_keys=True, allow_nan=False)+'\n'
                            for row in values))


def road():
    return '''<?xml version="1.0" encoding="UTF-8"?>
<OpenDRIVE><header revMajor="1" revMinor="4" name="C10374 alley safety zone" version="1.00" date="2026-11-08" north="0" south="-7" east="150" west="0" vendor="worker"/>
<road name="alley with pedestrian-only safety-zone request" length="150" id="374" junction="-1">
<type s="0" type="town"><speed max="20" unit="mph"/></type>
<planView><geometry s="0" x="0" y="0" hdg="0" length="150"><line/></geometry></planView>
<lanes><laneSection s="0"><center><lane id="0" type="none" level="false"><roadMark sOffset="0" type="solid" color="yellow" width="0.15"/></lane></center><right>
<lane id="-1" type="driving" level="false"><width sOffset="0" a="3.5" b="0" c="0" d="0"/><roadMark sOffset="0" type="solid" color="white" width="0.12"/></lane>
<lane id="-2" type="driving" level="false"><width sOffset="0" a="3.5" b="0" c="0" d="0"/><roadMark sOffset="0" type="solid" color="white" width="0.12"/></lane>
</right></laneSection>
<laneSection s="40"><center><lane id="0" type="none" level="false"><roadMark sOffset="0" type="solid" color="yellow" width="0.15"/></lane></center><right>
<lane id="-1" type="sidewalk" level="false"><width sOffset="0" a="3.5" b="0" c="0" d="0"/><roadMark sOffset="0" type="solid" color="white" width="0.20"/></lane>
<lane id="-2" type="driving" level="false"><width sOffset="0" a="3.5" b="0" c="0" d="0"/><roadMark sOffset="0" type="solid" color="white" width="0.12"/></lane>
</right></laneSection>
<laneSection s="60"><center><lane id="0" type="none" level="false"><roadMark sOffset="0" type="solid" color="yellow" width="0.15"/></lane></center><right>
<lane id="-1" type="driving" level="false"><width sOffset="0" a="3.5" b="0" c="0" d="0"/><roadMark sOffset="0" type="solid" color="white" width="0.12"/></lane>
<lane id="-2" type="driving" level="false"><width sOffset="0" a="3.5" b="0" c="0" d="0"/><roadMark sOffset="0" type="solid" color="white" width="0.12"/></lane>
</right></laneSection></lanes><objects/><signals/></road></OpenDRIVE>
'''


def build():
    assignment = ROOT/'inputs'/CASE.name/'assignment.json'
    frozen = json.loads(assignment.read_text())
    plan = json.loads((CASE/'case-plan.json').read_text())
    if (frozen['law_record']['text'] != LAW or plan['source_law']['text'] != LAW or
            frozen['cell']['layout'] != 'alley' or
            frozen['cell']['control'] != 'safety_zone' or
            frozen['actor'] != 'motor_vehicle_driver'):
        raise ValueError('frozen safety-zone source or cell differs')
    road_path = HERE/'alley-zone.xodr'
    road_path.write_text(road())
    entries = []
    for suffix, through in ((CASES[0], True), (CASES[1], False)):
        for candidate, (speed, camera, stop) in POLICIES.items():
            target = HERE/'drafts'/suffix/candidate
            case_id = CASE.name+'__'+suffix
            values = []
            for frame in range(240):
                t = (frame+1)/20
                x = min(stop if stop is not None else 150, 5+speed*t)
                y = -1.75 if through else -5.25
                values.append({'frame': frame, 'time_s': t,
                    'case_id': case_id, 'candidate_id': candidate,
                    'source_kind': 'authored_native_request',
                    'requested_ego_x_m': round(x, 6), 'requested_ego_y_m': y,
                    'requested_lane_id': -1 if through else -2,
                    'zone_x_min_m': ZONE[0], 'zone_x_max_m': ZONE[1],
                    'zone_y_min_m': ZONE[2], 'zone_y_max_m': ZONE[3],
                    'requested_zone_route': through,
                    'physical_zone_designation_verified': False,
                    'actual_zone_overlap_observed': False,
                    'legal_verdict': None})
            tracks = target/'requested-tracks.jsonl'
            put_rows(tracks, values)
            config = {'format': 'c10374-safety-zone-native-request-v1',
                'assignment_id': CASE.name, 'case_id': case_id,
                'candidate_id': candidate,
                'source_branch': 'NRS 484B.110', 'source_text': LAW,
                'assignment_sha256': sha(assignment),
                'case_plan_sha256': sha(CASE/'case-plan.json'),
                'road_sha256': sha(road_path), 'tracks_sha256': sha(tracks),
                'rate_hz': 20, 'frames': 240,
                'requested_ego_speed_mps': speed, 'camera_policy': camera,
                'stop_x_m': stop, 'zone_rectangle_xy_m': list(ZONE),
                'requested_zone_route': through,
                'physical_zone_designation_verified': False,
                'actual_zone_overlap_observed': False,
                'original_native_observed': False,
                'status': 'unselected_native_request'}
            put(target/'config.json', config)
            entries.append({'case_id': case_id, 'candidate_id': candidate,
                            'config_sha256': sha(target/'config.json'),
                            'tracks_sha256': sha(tracks),
                            'status': 'unselected_native_request'})
    manifest = {'format': 'c10374-safety-zone-native-construction-v1',
        'assignment_id': CASE.name, 'assignment_sha256': sha(assignment),
        'case_plan_sha256': sha(CASE/'case-plan.json'),
        'road_sha256': sha(road_path),
        'capture_sha256': sha(HERE/'capture.py'),
        'measurement_contract_sha256': sha(HERE/'measurement-contract.json'),
        'saved_sha256': sha(HERE/'saved.py'),
        'fixture_raw_sha256': sha(HERE/'fixture_raw.py'),
        'route_fallbacks_sha256': sha(HERE/'route_fallbacks.py'),
        'entries': entries, 'original_native_observed': False,
        'delivery_ready': False}
    put(HERE/'manifest.json', manifest)
    return manifest


if __name__ == '__main__':
    print(json.dumps({'requests': len(build()['entries'])}))
