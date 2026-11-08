"""Build eight exact, unselected inner/outer-lane Native circulation requests."""
import hashlib
import json
import math
from pathlib import Path

HERE=Path(__file__).resolve().parent
CASE=HERE.parent
ROOT=CASE.parents[1]

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def build():
    assignment=ROOT/'inputs'/CASE.name/'assignment.json'
    plan=CASE/'case-plan.json'
    road=HERE/'road.xodr'
    entries=[]
    for witness,lane,radius in (('witness_1',-1,23.75),('witness_2',-2,27.25)):
        for candidate in ('primary','fallback1','fallback2','fallback3'):
            speed=6.5 if candidate=='fallback1' else 3 if candidate=='fallback3' else 8
            camera='elevated_overview_plus_four' if candidate=='fallback2' else 'four_views'
            folder=HERE/'drafts'/witness/candidate
            folder.mkdir(parents=True,exist_ok=True)
            rows=[]
            for frame in range(240):
                time_s=(frame+1)/20
                travel=min(12,speed*time_s) if candidate=='fallback3' else speed*time_s
                theta=-math.pi/2+travel/radius
                rows.append({'frame':frame,'time_s':time_s,
                    'source_kind':'authored_native_request','witness':witness,
                    'candidate_id':candidate,'ego_x_m':round(radius*math.cos(theta),6),
                    'ego_y_m':round(radius*math.sin(theta),6),
                    'ego_heading_deg':round(math.degrees(theta+math.pi/2)%360,6),
                    'ego_speed_mps':0 if candidate=='fallback3' and speed*time_s>12 else speed,
                    'lane_id':lane,'requested_radius_m':radius,
                    'intended_exit_kind':'left_turn','actual_exit_observed':False,
                    'roundabout_verified':False})
            track=folder/'requested-tracks.jsonl'
            track.write_text(''.join(json.dumps(row,sort_keys=True)+'\n' for row in rows))
            config={'format':'c131364-roundabout-lane-request-v1',
                'assignment_id':CASE.name,'case_id':CASE.name+'__'+witness,
                'candidate_id':candidate,'law_id':'LVMC-11-43-010-C1',
                'cell_id':'C131364','actor':'motor_vehicle_driver',
                'rate_hz':20,'frames':240,'duration_s':12,
                'assignment_sha256':sha(assignment),'case_plan_sha256':sha(plan),
                'road_sha256':sha(road),'tracks_sha256':sha(track),
                'requested_lane_id':lane,'requested_lane_radius_m':radius,
                'camera_policy':camera,'ego_blueprint_request':'vehicle.tesla.model3',
                'weather_request':'ClearNoon','exit_connector_verified':False,
                'actual_left_exit_observed':False,'roundabout_verified':False,
                'status':'unselected_native_request'}
            (folder/'config.json').write_text(json.dumps(config,indent=2)+'\n')
            entries.append({'case_id':config['case_id'],'candidate_id':candidate,
                'config_sha256':sha(folder/'config.json'),
                'tracks_sha256':sha(track),'status':config['status']})
    manifest={'format':'c131364-construction-manifest-v1',
        'assignment_id':CASE.name,'assignment_sha256':sha(assignment),
        'case_plan_sha256':sha(plan),'road_sha256':sha(road),'entries':entries,
        'original_native_observed':False,'exit_connector_verified':False,
        'actual_left_exit_observed':False,'delivery_ready':False}
    (HERE/'drafts'/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    return manifest

if __name__=='__main__':print(json.dumps({'requests':len(build()['entries'])}))
