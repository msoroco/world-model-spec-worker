"""Build exact unselected rotary-island Native request candidates."""
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
    island=HERE/'island-geometry.json'
    entries=[]
    for case in ('reference','contrast'):
        direction=1 if case=='reference' else -1
        start=-math.pi/2 if case=='reference' else math.pi/2
        for candidate in ('primary','fallback1','fallback2','fallback3'):
            radius=27.25 if candidate=='fallback2' else 23.75
            lane=-2 if candidate=='fallback2' else -1
            speed=6.5 if candidate=='fallback1' else 3 if candidate=='fallback3' else 8
            folder=HERE/'drafts'/case/candidate
            folder.mkdir(parents=True,exist_ok=True)
            rows=[]
            for frame in range(240):
                t=(frame+1)/20
                distance=min(12,speed*t) if candidate=='fallback3' else speed*t
                angle=start+direction*distance/radius
                heading=(math.degrees(angle+direction*math.pi/2)%360)
                rows.append({'frame':frame,'time_s':t,
                    'source_kind':'authored_native_request',
                    'case':case,'candidate_id':candidate,
                    'ego_x_m':round(radius*math.cos(angle),6),
                    'ego_y_m':round(radius*math.sin(angle),6),
                    'ego_heading_deg':round(heading,6),
                    'ego_speed_mps':0 if candidate=='fallback3' and speed*t>12 else speed,
                    'lane_id':lane,'requested_radius_m':radius,
                    'island_center_xy_m':[0,0],
                    'physical_island_verified':False})
            track=folder/'requested-tracks.jsonl'
            track.write_text(''.join(json.dumps(row,sort_keys=True)+'\n' for row in rows))
            config={'format':'c234827-native-request-v1',
                'assignment_id':CASE.name,
                'case_id':CASE.name+'__'+case,
                'candidate_id':candidate,'island_side_request':case,
                'law_id':'NRS-484B-220-2','cell_id':'C234827',
                'actor':'motor_vehicle_driver',
                'rate_hz':20,'frames':240,'duration_s':12,
                'assignment_sha256':sha(assignment),
                'case_plan_sha256':sha(plan),
                'road_sha256':sha(road),
                'island_geometry_sha256':sha(island),
                'tracks_sha256':sha(track),
                'ego_blueprint_request':'vehicle.tesla.model3',
                'weather_request':'ClearNoon',
                'physical_island_verified':False,
                'status':'unselected_native_request'}
            (folder/'config.json').write_text(json.dumps(config,indent=2)+'\n')
            entries.append({'case_id':config['case_id'],'candidate_id':candidate,
                'config_sha256':sha(folder/'config.json'),
                'tracks_sha256':sha(track),'status':config['status']})
    manifest={'format':'c234827-native-construction-manifest-v1',
        'assignment_id':CASE.name,'assignment_sha256':sha(assignment),
        'case_plan_sha256':sha(plan),'road_sha256':sha(road),
        'island_geometry_sha256':sha(island),
        'entries':entries,'original_native_observed':False,
        'physical_island_verified':False,'delivery_ready':False}
    (HERE/'drafts'/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    return manifest


if __name__=='__main__':print(json.dumps({'requests':len(build()['entries'])}))
