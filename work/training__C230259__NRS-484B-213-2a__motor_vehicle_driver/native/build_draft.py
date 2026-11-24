"""Materialize two exact unselected inline constructions against pinned offline API."""
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
HERE=Path(__file__).resolve().parent
OTHER=Path('work/training__C102951__NRS-484B-213-1__motor_vehicle_driver/native/road.xodr')
ROAD=OTHER.read_text().replace('C102951','C230259')


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path,obj):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(obj,indent=2,ensure_ascii=False)+'\n')


def config(suffix):
    case=ROOT.name+'__'+suffix
    if suffix=='probe_a':
        phases=[('approach',0,239,'-1'),('crest',240,399,'-1'),('departure',400,599,'-1')]
    else:
        phases=[('approach',0,239,'-1'),('crest',240,399,'1'),('departure',400,599,'-1')]
    return {'case_id':case,'selected_case_id':case,'law_id':'NRS-484B-213-2a',
            'cell_id':'C230259','actor':'motor_vehicle_driver','rate_hz':20,
            'duration_s':30,'duration_frames':600,
            'cameras':[{'name':n,'fps':20,'width':w,'height':h} for n,w,h in
                       [('overview',1920,1080),('approach',1280,720),
                        ('reference_corner',1280,720),('driver_reference',1280,720)]],
            'road_directionality':'two_way','ego_lane_id':'-1','opposing_lane_id':'1',
            'ego_spawn':{'road_id':'1','lane_id':'-1','s_m':300},
            'other_vehicle':{'route_direction':'opposing','lane_id':'1','spawn_s_m':560,
                             'identity':'opposing_vehicle'},
            'control_phases':[{'name':n,'first_frame':a,'last_frame':b,'target_lane_id':lane,
                               'target_speed_mps':5.0} for n,a,b,lane in phases],
            'acquire':['original_ego_transform','ego_bounding_box','original_other_vehicle_transform',
                       'road_elevation_readback','sightline_rays','four_source_camera_frames'],
            'hazard_distance_legal_judgment':None,'physical_verified':False,'legal_verdict':None}


def main():
    cases=[]
    for suffix in ('probe_a','probe_b'):
        c=config(suffix);case=c['case_id']
        construction={'format':'worker-inline-construction','case_id':case,
                      'cell_id':'C230259','law_id':'NRS-484B-213-2a','actor':'motor_vehicle_driver',
                      'entrypoint':'runner.py','status':'draft_cpu_offline_only',
                      'files':[{'path':'config.json','content':json.dumps(c,indent=2)+'\n'},
                               {'path':'road.xodr','content':ROAD},
                               {'path':'runner.py','content':(HERE/'draft_runner.py').read_text()},
                               {'path':'tests/test_offline.py','content':(HERE/'test_draft_offline.py').read_text()}],
                      'recording_description':{'channels':[{'name':'source_geometry_and_sight_brackets',
                        'method':'original Native transforms, bounding boxes, elevation and sightline readback',
                        'sampling_rate_hz':20,'time_window':'600 frames'},
                        {'name':'four_source_cameras','method':'synchronized source pixels',
                         'sampling_rate_hz':20,'time_window':'600 frames'}],
                        'limitations':['Original Native crest sightline and legal hazard judgment unverified']}}
        path=ROOT/'draft-cases'/suffix/'primary/construction.json';write(path,construction)
        cases.append({'case_id':case,'kind':'draft_not_selected',
                      'construction':str(path.relative_to(ROOT)),'construction_sha256':sha(path),
                      'candidate_risk':{'status':'physical','reason':'Crest visibility and lateral motion require original Native evidence.'}})
    manifest={'format':'worker-unselected-draft-construction-manifest-v1',
              'assignment_id':ROOT.name,'status':'draft_cpu_offline_only','cases':cases,
              'original_native_observed':False,'delivery_ready':False}
    target=ROOT/'draft-manifest.json';write(target,manifest)
    print(json.dumps({'manifest_sha256':sha(target),'cases':cases}))

if __name__=='__main__':main()
