"""Build bounded synthetic C42387 source specifications for CPU proof only."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

from geometry import open_drive
from measure_observed import CASE_PREFIX

HERE = Path(__file__).resolve().parent
ASSIGNMENT = HERE.parent
ROOT = ASSIGNMENT.parents[1]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def lines(rows):
    return ''.join(json.dumps(row, separators=(',', ':'), allow_nan=False) + '\n' for row in rows)


def create(suffix):
    case = CASE_PREFIX + suffix
    target = {'a':35,'b':20,'c':30.48}[suffix]
    signal_frame = {'a':212,'b':250,'c':224}[suffix]
    samples, mapping, bodies, trace, evidence, frames, graphs = [], [], [], [], [], [], []
    for index in range(600):
        frame, time = 1000 + index, index / 20
        if index <= 300:
            x, y, heading, road_id = -120 + .4 * index, 1.75, 0.0, 1
        else:
            angle = min((index - 300) * .4 / 18, math.pi / 2)
            x = 18 * math.sin(angle)
            y = 1.75 - 18 + 18 * math.cos(angle)
            heading = -math.degrees(angle)
            road_id = 2 if index > 330 else 1
            if angle >= math.pi / 2:
                y -= (index - 300 - math.pi * 18 / .8) * .4
        c, s = math.cos(math.radians(heading)), math.sin(math.radians(heading))
        footprint = [[round(x + u*c-v*s, 6), round(y + u*s+v*c, 6), z]
            for u, v in ((-2,-.8),(-2,.8),(2,-.8),(2,.8)) for z in (0,1.5)]
        observed = signal_frame <= index < 500
        sample = {'provenance':'synthetic_cpu_fixture','case_id':case,
            'sample_index':index,'native_frame':frame,'time_s':time,
            'ego_center_xy_m':[round(x,6),round(y,6)],'ego_heading_deg':heading,
            'ego_speed_mps':8.0,'road_id':road_id,'lane_id':-1,
            'right_lamp_commanded':observed,'right_lamp_observed':observed,
            'course_change_observed':index>=301,
            'area_classification':'business_district','precipitation':'clear'}
        samples.append(sample)
        mapping.append({'video_frame':index,'carla_frame':frame,'native_frame':frame,'time_s':time})
        bodies.append({'frame':frame,'time_s':time,'road_id':road_id,'lane_id':-1,
                       'body_vertices_m':footprint})
        trace.append({'frame':frame,'time_s':time,'position':{'x':x,'y':y,'z':.5},
            'position_m':[x,y,.5],'heading_deg':heading,'speed_mps':8.0,
            'speed_mph':8/.44704,
            'velocity_mps':[8*c,8*s,0.0],
            'control':{'throttle':0,'brake':0,'hand_brake':False}})
        evidence.append({'original_frame':frame,'recording_time_s':time,
            'replay_frame':frame,'replay_simulation_time_s':time,'actor_id':107,
            'ego':{'body_vertices_m':footprint,'position_m':[x,y,.5],
                   'heading_deg':heading,'speed_mps':8.0,
                   'speed_provenance':'synthetic_native_sample','synthetic_diagnostic':True},
            'world':{'weather':{'cloudiness':0,'precipitation':0,'wetness':0,'fog_density':0},
                'road_projection':{'road_id':road_id,'section_id':0,'lane_id':-1,'s_m':x+130}}})
        graph_path = f'capture/native/graphs/base/{frame:08d}.adapter.json'
        frames.append({'frame':frame,'simulation_time':time,'time_s':time,
            'base':f'graphs/base/{frame:08d}.adapter.json',
            'adapter_graph':f'graphs/base/{frame:08d}.adapter.json',
            'synthetic_diagnostic':True})
        graphs.append({'path':graph_path,'attributes':{'frame':frame},'nodes':[],'edges':[]})
    map_text = open_drive()
    files = {'road.xodr':map_text,
        'road_geometry.json':json.dumps({'authored_map_sha256':hashlib.sha256(map_text.encode()).hexdigest(),
            'native_map_sha256':'a'*64,'approach_road_id':1,'destination_road_id':2,
            'area_classification':'business_district','area_classification_review_required':True,
            'provenance':'synthetic_cpu_fixture'})+'\n',
        'control_context.json':json.dumps({'control':'other_vehicle',
            'native_blueprint':'vehicle.lincoln.mkz_2020','native_actor_id':23})+'\n',
        'native_samples.jsonl':lines(samples),'video_frames.jsonl':lines(mapping),
        'body_history.jsonl':lines(bodies),'trace.jsonl':lines(trace),
        'capture/evidence.jsonl':lines(evidence),
        'capture/native/frames.jsonl':lines(frames),
        'capture/recorder_info.txt':'Create 107: vehicle.lincoln.mkz_2020\n'}
    files['capture/manifest.json'] = json.dumps({'extraction_confirmed':True,
        'frames':600,'synthetic_diagnostic':True,
        'sources':{'road.xodr':hashlib.sha256(map_text.encode()).hexdigest(),
                   'trace.jsonl':hashlib.sha256(files['trace.jsonl'].encode()).hexdigest()}})+'\n'
    videos = [{'path':name+'.mkv','frames':600,'width':width,'height':height,
        'fps':20,'color':'black'} for name,width,height in
        (('overview',1920,1080),('approach',1280,720),
         ('reference_corner',1280,720),('driver_reference',1280,720))]
    spec = ASSIGNMENT / f'native/selected-{suffix}-fixture.json'
    spec.write_text(json.dumps({'files':files,'graphs':graphs,'videos':videos},
        separators=(',', ':'), allow_nan=False)+'\n')
    source = ROOT / 'inputs' / ASSIGNMENT.name / 'assignment.json'
    recipe = ASSIGNMENT / f'native/selected-{suffix}-fixture-recipe.json'
    recipe.write_text(json.dumps({'format':'worker-fixture-recipe',
        'sources':[{'path':'diagnostic-input-assignment.json',
                    'source':str(source.relative_to(ROOT)),'sha256':sha(source)}],
        'generator':{'source':str(spec.relative_to(ROOT)),'sha256':sha(spec)}},
        indent=2)+'\n')
    if spec.stat().st_size > 2*1024*1024:
        raise ValueError('Fixture specification exceeds return file limit')
    return {'case_id':case,'spec':str(spec.relative_to(ROOT)),
            'spec_bytes':spec.stat().st_size,'spec_sha256':sha(spec),
            'recipe':str(recipe.relative_to(ROOT)),'recipe_sha256':sha(recipe),
            'target_m':target}


if __name__ == '__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--condition',choices=('a','b','c'),required=True)
    args=parser.parse_args()
    print(json.dumps(create(args.condition),sort_keys=True))
