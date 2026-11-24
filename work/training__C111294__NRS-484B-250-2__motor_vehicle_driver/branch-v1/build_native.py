"""Author exact original-Native branch requests from source-hashed CPU controls."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASE = HERE.parent
REPO = BASE.parents[1]
FROZEN = REPO/'inputs'/BASE.name/'assignment.json'
PLAN = BASE/'case-plan.json'
CASES = ('device_controlled','opposing_no_turn','opposing_left_turn')
POLICIES = {'primary':(5.0,'standard'),
            'fallback1':(4.5,'standard'),
            'fallback2':(5.0,'elevated_overview')}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path,obj):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(obj,indent=2,sort_keys=True)+'\n')


def build(suffix,candidate):
    if suffix not in CASES or candidate not in POLICIES:
        raise ValueError('Unknown exact branch request')
    if sha(FROZEN)!='d005cde0eec41f63fcc0dc8aedb3a3d81c39daa3ed8b2d193fca4161769dd738':
        raise ValueError('Frozen assignment changed')
    speed,camera=POLICIES[candidate]
    case_id=BASE.name+'__'+suffix
    source=HERE/suffix/'sources'
    history=json.loads((source/'actor-history.json').read_text())
    if len(history['rows'])!=600 or history['case_id']!=case_id:
        raise ValueError('Branch source geometry missing')
    bundle=HERE/suffix/candidate/'native-request'
    bundle.mkdir(parents=True,exist_ok=True)
    (bundle/'assignment-source.json').write_bytes(FROZEN.read_bytes())
    (bundle/'case-plan.json').write_bytes(PLAN.read_bytes())
    (bundle/'crossroads.xodr').write_bytes((source/'road.xodr').read_bytes())
    tracks=[]
    for row in history['rows']:
        other=row['other']
        ego=row['ego']
        tracks.append({'frame':row['frame'],'time_s':row['time_s'],
                       'requested_ego_xyz_m':ego['center_xyz_m'],
                       'requested_other_xyz_m':other['center_xyz_m'],
                       'requested_ego_heading_rad':0.0,
                       'requested_other_heading_rad':other.get('yaw_rad',1.570796327),
                       'requested_ego_speed_mps':speed,
                       'requested_ego_phase':('approach' if ego['center_xyz_m'][0]<-20 else
                                              'intersection' if ego['center_xyz_m'][0]<20 else
                                              'departure'),
                       'requested_other_speed_mps':other['speed_mps'],
                       'requested_other_left_turn_intent':row['other_left_turn_intent'],
                       'requested_opposing_approaches':row['opposing_approaches'],
                       'authored_official_device_count':row['authored_official_device_count'],
                       'original_native_observed':False,'legal_verdict':None})
    track=bundle/'requested-tracks.jsonl'
    track.write_text(''.join(json.dumps(row,sort_keys=True)+'\n' for row in tracks))
    config={'format':'c111294-2502-branch-native-request-v1',
            'assignment_id':BASE.name,'case_id':case_id,'candidate_id':candidate,
            'assignment_sha256':sha(FROZEN),'case_plan_sha256':sha(PLAN),
            'road_sha256':sha(bundle/'crossroads.xodr'),'tracks_sha256':sha(track),
            'source_text':json.loads(FROZEN.read_text())['law']['text'],
            'rate_hz':20,'frames':600,
            'ego_highway_road_ids':[250,251,252],
            'other_highway_road_ids':[250,251,252] if suffix.startswith('opposing_') else [253,254,255],
            'ego_entry_boundary_x_m':-20,
            'other_entry_boundary_m':20 if suffix.startswith('opposing_') else -20,
            'requested_speed_mps':speed,'camera_policy':camera,
            'requested_other_left_turn_intent':suffix=='opposing_left_turn',
            'requested_opposing_approaches':suffix.startswith('opposing_'),
            'authored_official_device_count':int(suffix=='device_controlled'),
            'ego_blueprint':'vehicle.tesla.model3',
            'other_blueprint':'vehicle.audi.a2',
            'status':'unselected_native_request',
            'original_native_observed':False,'legal_verdict':None}
    write(bundle/'config.json',config)
    return {'case_id':case_id,'candidate':candidate,'config_sha256':sha(bundle/'config.json'),
            'tracks_sha256':sha(track),'road_sha256':sha(bundle/'crossroads.xodr')}


if __name__=='__main__':
    print(json.dumps([build(suffix,candidate) for suffix in CASES for candidate in POLICIES]))
