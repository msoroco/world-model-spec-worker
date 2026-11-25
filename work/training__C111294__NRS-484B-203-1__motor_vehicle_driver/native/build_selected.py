"""Materialize exact source-hashed selected Native construction drafts."""
import hashlib
import json
from pathlib import Path
from route import requested_rows

PKG = Path(__file__).resolve().parents[1]
NATIVE = Path(__file__).resolve().parent
ASSIGNMENT = PKG.name
CAMERAS = [
    {'name':'overview','width':1920,'height':1080,'fov_deg':85,'pose_strategy':'fixed_overhead_meeting'},
    {'name':'approach','width':1280,'height':720,'fov_deg':85,'pose_strategy':'fixed_ego_approach'},
    {'name':'reference_corner','width':1280,'height':720,'fov_deg':85,'pose_strategy':'fixed_opposite_lane_side'},
    {'name':'driver_reference','width':1280,'height':720,'fov_deg':85,'pose_strategy':'fixed_ego_side_reference'}]


def sha(data): return hashlib.sha256(data).hexdigest()


def build(case, candidate='primary'):
    aid = ASSIGNMENT + '__' + case
    folder = NATIVE/'bundles'/case
    folder.mkdir(parents=True,exist_ok=True)
    assignment = Path('inputs')/ASSIGNMENT/'assignment.json'
    if candidate not in ('primary', 'fallback1'):
        raise ValueError('Unknown exact candidate')
    config = {'case_id':aid,'case_suffix':case,'selected_case_id':aid,'case':{'case_id':aid},
        'candidate_id':candidate,'cell_id':'C111294','law_id':'NRS-484B-203-1',
        'actor':'motor_vehicle_driver','assignment_sha256':sha(assignment.read_bytes()),
        'law_text':json.loads(assignment.read_text())['law']['text'],
        'rate_hz':20,'duration_s':30,'frames':600,
        'spawn_z_m':1.5 if candidate=='primary' else 1.8,
        'source_kind':'synthetic_scene_request','native_observed':False,
        'required_atoms':[],'source_packets':[],'cameras':CAMERAS,'supported_case_ids':[aid]}
    rows = ''.join(json.dumps(r,allow_nan=False)+'\n' for r in requested_rows(case))
    config['request_sha256']=sha(rows.encode())
    config_text = json.dumps(config,indent=2)+'\n'
    files = [
        {'path':'assignment-source.json','source':str(assignment),'content':assignment.read_text()},
        {'path':'request.jsonl','content':rows},
        {'path':'config.json','content':config_text}]
    for name in ('road.xodr','route.py','check.py','runner.py','meeting_math.py',
                 'measure_saved.py','finalize.py','tests/test_request.py'):
        source = NATIVE/name
        files.append({'path':name,'source':str(source),'content':source.read_text()})
    description = {'channels':[
        {'name':'ego_body','unit':'structured','method':'original Native body vertices','sampling_rate_hz':20,'time_window':'600 frames','reference_frame':'Native world and frame','uncertainty':'original road/body review pending'},
        {'name':'oncoming_body','unit':'structured','method':'original Native body vertices','sampling_rate_hz':20,'time_window':'600 frames','reference_frame':'Native world and frame','uncertainty':'original road/body review pending'},
        {'name':'paved_road_context','unit':'structured','method':'OpenDRIVE lane readback plus original pavement edge review','sampling_rate_hz':20,'time_window':'600 frames','reference_frame':'Native road 111294','uncertainty':'authored boundaries are not verified original pavement edges'},
        {'name':'meeting_motion','unit':'structured','method':'original Native actor velocities and positions','sampling_rate_hz':20,'time_window':'600 frames','reference_frame':'Native world and frame','uncertainty':'50 ms frame bracket'}],
        'context_inputs':[],
        'limitations':['Original pavement edges and as-nearly-as-possible physical context require separate review.',
                       'Body-footprint fraction is an engineering diagnostic, not statutory half allocation.']}
    construction = {'case_id':aid,'cell_id':'C111294','law_id':'NRS-484B-203-1',
        'actor':'motor_vehicle_driver','entrypoint':'runner.py','files':files,
        'recording_description':description,'status':'selected_native_draft',
        'static_checks':['authored opposing driving lanes','600-frame two-body request',
            'four source cameras','Native original actor and pavement source capture']}
    path=folder/('construction.json' if candidate=='primary' else 'fallback1.json')
    path.write_text(json.dumps(construction,indent=2)+'\n')
    return {'case_id':aid,'candidate_id':candidate,
            'construction':str(path.relative_to(PKG)),
            'construction_sha256':sha(path.read_bytes()),'kind':'delivery'}


if __name__=='__main__':
    print(json.dumps([build(case,candidate) for case in ('0.45','0.55')
                      for candidate in ('primary','fallback1')],indent=2))
