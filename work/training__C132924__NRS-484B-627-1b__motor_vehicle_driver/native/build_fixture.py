"""Build source-hashed roundabout software fixtures, never physical evidence."""

import hashlib
import json
import math
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REPO = ROOT.parents[1]
SCRATCH = Path(os.environ['SCENARIO_PIPELINE_OUTPUT_ROOT'])
BASE = REPO/'work/training__C230266__NRS-484B-280-1c__motor_vehicle_driver/selected-generator-probe_1.json'
CAMERAS = ('overview','approach','reference_corner','driver_reference')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,separators=(',',':'),ensure_ascii=False)+'\n')


def lines(rows):
    return ''.join(json.dumps(row,separators=(',',':'),allow_nan=False)+'\n' for row in rows)


def actor(radius,angle,speed):
    x,y = radius*math.cos(angle),radius*math.sin(angle)
    return {'x_m':round(x,7),'y_m':round(y,7),'speed_mps':speed,
            'body_vertices_native_m':[[round(x+dx,7),round(y+dy,7),z] for dx,dy,z in
                ((-.1,-.1,0),(-.1,.1,0),(.1,-.1,0),(.1,.1,0),
                 (-.1,-.1,1.5),(-.1,.1,1.5),(.1,-.1,1.5),(.1,.1,1.5))]}


def build():
    base = json.loads(BASE.read_text())
    plan = json.loads((ROOT/'case-plan.json').read_text())
    results = []
    for case in plan['cases']:
        case_id = case['case_id']
        suffix = case_id.rsplit('__',1)[-1]
        pass_case = suffix in ('necessary_pass','post_pass_linger')
        source_dir = ROOT/'selected-source'/suffix
        source_dir.mkdir(parents=True,exist_ok=True)
        geometry = source_dir/'geometry.json'
        write(geometry,{'source_kind':'synthetic_native_sample','case_id':case_id,
                        'direction':'counterclockwise','center_xy_m':[0,0],
                        'outer_right_lane_radius_m':[13.0,16.0],
                        'inner_left_lane_radius_m':[10.0,13.0],
                        'same_direction_marked_lanes_source':'synthetic diagnostic annular rings, not original Native road markings',
                        'lane_marking_source':'synthetic diagnostic rings'})
        files = {name:value for name,value in base['files'].items()
                 if name not in ('pedestrian-caution-trace.jsonl','pedestrian-source-review.jsonl',
                                 'context-survey.json','trace.jsonl','capture/evidence.jsonl',
                                 'video_frames.jsonl','capture/manifest.json')}
        native,trace,evidence,frame_map = [],[],[],[]
        for i in range(600):
            t = i/20
            radius = 14.5 if suffix == 'probe_a' or (suffix == 'necessary_pass' and i >= 300) else 11.5
            theta = 3.0*t/radius
            ego = actor(radius,theta,3.0)
            follower = actor(radius,theta-.1,5.0)
            participants = {'ego':ego,'follower':follower}
            observation = None
            if pass_case:
                slow_theta = 1.0344827586+2.0*t/14.5
                participants['slower_vehicle'] = actor(14.5,slow_theta,2.0)
                observation = {'slower_vehicle_ahead':i<300,
                               'slower_vehicle_cleared':i>=300,
                               'source_actor_id':303}
            fid = 2000+i
            native.append({'source_kind':'synthetic_native_sample','native_frame':fid,
                           'time_s':t,'actors':participants,'pass_observation':observation,
                           'requested_phase':'diagnostic_only','legal_verdict':None})
            velocity = [-3*math.sin(theta),3*math.cos(theta),0]
            trace.append({'frame':fid,'time_s':t,'position':{'x':ego['x_m'],'y':ego['y_m'],'z':1},
                          'position_m':[ego['x_m'],ego['y_m'],1],
                          'heading_deg':math.degrees(theta+math.pi/2)%360,
                          'speed_mps':3.0,'speed_mph':6.7108088763,
                          'control':{'throttle':.2,'brake':0,'hand_brake':False},
                          'synthetic_diagnostic':True,'velocity_mps':velocity,
                          'speed_provenance':'synthetic_native_sample'})
            evidence.append({'original_frame':fid,'replay_frame':fid,'actor_id':101,
                             'recording_time_s':t,'replay_simulation_time_s':t,
                             'ego':{'position_m':[ego['x_m'],ego['y_m'],1],
                                    'heading_deg':math.degrees(theta+math.pi/2)%360,
                                    'speed_mps':3.0,'speed_provenance':'synthetic_native_sample',
                                    'body_vertices_m':ego['body_vertices_native_m']},
                             'world':{'weather':{'cloudiness':0,'precipitation':0,
                                                  'wetness':0,'fog_density':0},
                                      'road_projection':{'road_id':1,'section_id':0,
                                                         'lane_id':-1 if radius==14.5 else -2,
                                                         's_m':100+3*t}}})
            frame_map.append({'video_frame':i,'carla_frame':fid,'native_frame':fid,
                              'time_s':t,'source_cameras':{name:fid for name in CAMERAS}})
        files['native.jsonl'] = lines(native)
        files['trace.jsonl'] = lines(trace)
        files['capture/evidence.jsonl'] = lines(evidence)
        files['video_frames.jsonl'] = lines(frame_map)
        files['capture/manifest.json'] = json.dumps({
            'extraction_confirmed':True,'frames':600,'required_observations':[],
            'synthetic_diagnostic':True,
            'sources':{'trace.jsonl':hashlib.sha256(files['trace.jsonl'].encode()).hexdigest(),
                       'geometry.json':sha(geometry),
                       'road.xodr':hashlib.sha256(files['road.xodr'].encode()).hexdigest()}},indent=2)+'\n'
        generator = {'files':files,'graphs':base['graphs'],'videos':base['videos']}
        generator_path = ROOT/('selected-generator-'+suffix+'.json')
        write(generator_path,generator)
        recipe = {'format':'worker-fixture-recipe',
                  'sources':[{'path':'geometry.json','source':str(geometry.relative_to(REPO)),
                              'sha256':sha(geometry)}],
                  'generator':{'source':str(generator_path.relative_to(REPO)),
                               'sha256':sha(generator_path)}}
        recipe_path = ROOT/('selected-recipe-'+suffix+'.json')
        write(recipe_path,recipe)
        results.append({'case_id':case_id,'generator':generator_path.name,
                        'generator_sha256':sha(generator_path),
                        'recipe':recipe_path.name,'recipe_sha256':sha(recipe_path)})
        print(json.dumps({'case':suffix,'generator_bytes':generator_path.stat().st_size}),flush=True)
    index = ROOT/'selected-fixture-index.json'
    write(index,{'format':'c132924-selected-fixtures-v1','cases':results})
    return {'cases':len(results),'index_sha256':sha(index)}


if __name__=='__main__':
    print(json.dumps(build()))
