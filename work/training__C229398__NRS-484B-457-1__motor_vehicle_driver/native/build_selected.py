"""Materialize seven exact C229398 parking bundles and risk-based angle fallbacks."""
import hashlib
import json
from pathlib import Path
import sys

PKG=Path(__file__).resolve().parents[1]
NATIVE=Path(__file__).resolve().parent
sys.path.insert(0,str(PKG))
from parking_scene import CASES,CAMERAS,request

ASSIGNMENT=PKG.name
CAMERA_CONFIG=[{'name':name,'width':width,'height':height,'fov_deg':85,
    'pose_strategy':{'overview':'fixed_overhead_parking',
                     'approach':'fixed_approach_lane',
                     'reference_corner':'fixed_curb_reference',
                     'driver_reference':'fixed_vehicle_side'}[name]}
    for name,width,height in CAMERAS]


def sha(data):return hashlib.sha256(data).hexdigest()


def build(suffix,candidate='primary'):
    if suffix not in CASES or candidate not in ('primary','fallback1') or (candidate=='fallback1' and not suffix.startswith('angle')):
        raise ValueError('Unknown parking candidate')
    cid=ASSIGNMENT+'__'+suffix
    folder=NATIVE/'bundles'/suffix;folder.mkdir(parents=True,exist_ok=True)
    assignment=Path('inputs')/ASSIGNMENT/'assignment.json'
    req=request(suffix)
    road=req['source_map']
    request_text=json.dumps(req,indent=2)+'\n'
    config={'case_id':cid,'selected_case_id':cid,'case':{'case_id':cid},
        'candidate_id':candidate,'cell_id':'C229398','law_id':'NRS-484B-457-1',
        'actor':'motor_vehicle_driver','assignment_sha256':sha(assignment.read_bytes()),
        'law_text':json.loads(assignment.read_text())['law']['text'],
        'rate_hz':20,'duration_s':30,'frames':600,
        'spawn_z_m':1.5 if candidate=='primary' else 1.8,
        'source_kind':'synthetic_scene_request','native_observed':False,
        'physical_completion':{'criterion':'travel_progress','motion_source':'trace.jsonl',
            'position_key':'position_m','minimum_progress_m':8.0,
            'completion_goal_method':'Original 8 m approach before stopped/parked interval; engineering milestone, not legal threshold'},
        'required_atoms':[],'source_packets':[],'cameras':CAMERA_CONFIG,
        'supported_case_ids':[cid],
        'case_target':{'parking_kind':req['parking_kind'],
                       'requested_gap_in':req['requested_gap_in'],
                       'requested_heading_deg':req['requested_heading_deg'],
                       'rest_mode':req['rest_mode']},
        'request_sha256':sha(request_text.encode())}
    files=[{'path':'assignment-source.json','source':str(assignment),
            'content':assignment.read_text()},
           {'path':'request.json','content':request_text},
           {'path':'road.xodr','content':road},
           {'path':'config.json','content':json.dumps(config,indent=2)+'\n'}]
    for name,source in (('parking_scene.py',PKG/'parking_scene.py'),
                        ('measure_parking.py',PKG/'measure_parking.py'),
                        ('runner.py',NATIVE/'runner.py'),
                        ('measure_saved.py',NATIVE/'measure_saved.py'),
                        ('finalize.py',NATIVE/'finalize.py'),
                        ('tests/test_request.py',NATIVE/'tests'/'test_request.py')):
        files.append({'path':name,'source':str(source.relative_to(Path.cwd())),
                      'content':source.read_text()})
    description={'channels':[
        {'name':name,'unit':'structured','method':method,'sampling_rate_hz':20,
         'time_window':'600 frames','reference_frame':'Native road 229398 and frame',
         'uncertainty':'original source and wheel/curb unit review pending'}
        for name,method in (
            ('ego_pose','original Native transform and body vertices'),
            ('wheel_curb_geometry','original wheel physics positions and curb readback'),
            ('parking_state','original speed and stopped/parked source history'),
            ('administrative_context','original ordinance and DOT source review'),
            ('right_wheel_curb_clearance','saved derived wheel edge to curb'))],
        'context_inputs':[],'limitations':['Original wheel units and curb surfaces require review.',
            'Local ordinance and DOT determination are administrative facts, not inferred from signs.',
            'Physical parking and camera visibility require original recording review.']}
    construction={'case_id':cid,'cell_id':'C229398','law_id':'NRS-484B-457-1',
        'actor':'motor_vehicle_driver','entrypoint':'runner.py','files':files,
        'recording_description':description,'status':'selected_native_draft',
        'measurement_plan':{'metric':'saved front and rear wheel outer edge to curb in inches',
                            'window':'every stopped or parked frame','source_review_required':True},
        'static_checks':['one-way same-direction driving lanes','two curbs',
                         '600-frame rest request','four synchronized camera sources'],
        'termination_rules':['600 frames','original capture seal and world restoration'],
        'mechanisms':['CARLA Native one-way road and curb objects',
                      'vehicle brake and handbrake rest request',
                      'original wheel physics source capture']}
    path=folder/('construction.json' if candidate=='primary' else 'fallback1.json')
    path.write_text(json.dumps(construction,indent=2)+'\n')
    return {'case_id':cid,'candidate_id':candidate,'construction':str(path.relative_to(PKG)),
            'construction_sha256':sha(path.read_bytes()),'kind':'delivery'}


if __name__=='__main__':
    print(json.dumps([build(s,c) for s in CASES for c in
        (('primary','fallback1') if s.startswith('angle') else ('primary',))],indent=2))
