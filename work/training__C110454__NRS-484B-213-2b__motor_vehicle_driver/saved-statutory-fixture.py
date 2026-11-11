"""C110454 positive and missing-source saved diagnostics; synthetic only."""
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'runtime/pipeline/scenario_pipeline'))
from worker_exchange.measurement_contract import verify_report
from batch_pipeline.carla import validate_attempt

ROOT=Path(__file__).resolve().parents[2]
FOLDER=Path(__file__).resolve().parent
FINALIZER=FOLDER/'native/finalize_statutory.py'
sys.path.insert(0,str(FOLDER/'native'))
from geometry_statutory import CASES,open_drive


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def write_rows(path,rows):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text('\n'.join(json.dumps(row) for row in rows)+'\n')


def source_digest(folder):
    return {str(p.relative_to(folder)):sha(p) for p in folder.rglob('*') if p.is_file() and p.name not in ('analysis-report.json','result.json')}


def make_base(destination,suffix,frame_count=4,full_resolution=False):
    destination.mkdir();(destination/'capture').mkdir()
    construction=json.loads((FOLDER/'draft-statutory-candidates'/suffix/'primary/construction.json').read_text())
    config=json.loads(next(f['content'] for f in construction['files'] if f['path']=='config.json'))
    if frame_count!=480:raise ValueError('Full 480-frame statutory fixture required')
    config['duration_s']=frame_count/20;config['rate_hz']=20
    (destination/'config.json').write_text(json.dumps(config))
    spec=CASES[suffix];one_way=spec['one_way'];rail=suffix.startswith('rail_')
    directions={'approach_forward':[1,0],'approach_opposing':[1,0] if one_way else [-1,0],
                'destination_forward':[1,0],'destination_opposing':[1,0] if one_way else [-1,0]}
    geometry={'native_map_sha256':'a'*64,'road_directions_native':directions,
              'approach_centerline_point_native_m':[0,0],
              'approach_right_normal_native':[0,-1], 'right_half_width_m':3.5,
              'intersection_entry_point_native_m':[-7,0],
              'approach_forward_native':[1,0],
              'destination_exit_point_native_m':[7,0],
              'destination_forward_native':[1,0],
              'railroad_crossing_native_readback':rail,
              'railroad_crossing_object_id':'701' if rail else None,
              'one_way_native_readback':one_way,'approach_zone_kind':spec['zone'],
              'approach_boundary_x_m':spec['boundary_x_m']}
    (destination/'road_geometry.json').write_text(json.dumps(geometry))
    (destination/'context.json').write_text(json.dumps({'surveyed_statutory_approach':geometry}))
    trace=[];evidence=[];mapping=[];motion=[];history=[]
    route=json.loads((FOLDER/'native/routes'/f'{suffix}.json').read_text())
    states=[(*route[min(round(i*(len(route)-1)/399),len(route)-1)],(1,0)) for i in range(frame_count)]
    for i,(x,y,forward) in enumerate(states):
        frame=100+i;t=.05*(i+1)
        fx,fy=forward;rx,ry=-fy,fx
        corners=[[x+direction*2.6*fx+side*1.1*rx,
                  y+direction*2.6*fy+side*1.1*ry]
                 for direction,side in ((-1,-1),(-1,1),(1,1),(1,-1))]
        body=[[a,b,z] for a,b in corners for z in (0,1.5)]
        trace.append({'frame':frame,'time_s':t,
                      'position':{'x':x,'y':y,'z':0.5},
                      'heading_deg':math.degrees(math.atan2(fy,fx)),
                      'speed_mps':0.0 if frame_count==480 and i>=450 else 5.0,
                      'synthetic_diagnostic':True,'speed_provenance':'synthetic_native_sample'})
        evidence.append({'original_frame':frame,'recording_time_s':t,
                         'synthetic_diagnostic':True,
                         'ego':{'body_vertices_m':body,'speed_provenance':'synthetic_native_sample'}})
        mapping.append({'video_frame':i,'native_frame':frame,'carla_frame':frame,'time_s':t})
        motion.append({'native_frame':frame,'time_s':t,'native_center_xy_m':[x,y],
                       'native_forward_xy':list(forward),'native_body_xy_m':corners,
                       'video_frame':i,'body_xy_m':corners,
                       'speed_m_s':0.0 if frame_count==480 and i>=450 else 5.0,
                       'two_way_native_survey':not one_way,'one_way_native_survey':one_way,
                       'synthetic_diagnostic':True,'speed_provenance':'synthetic_native_sample'})
        history.append({'frame':frame,'time_s':t,'body_vertices_m':body})
    for name,rows in [('trace.jsonl',trace),('capture/evidence.jsonl',evidence),
                      ('video_frames.jsonl',mapping),('native_samples.jsonl',motion),
                      ('body_history.jsonl',history)]:write_rows(destination/name,rows)
    (destination/'road.xodr').write_text(open_drive(suffix))
    (destination/'statutory_context.json').write_text(json.dumps({
        'source_kind':'native_statutory_context_schema','case_suffix':suffix,
        'zone_kind':spec['zone'],'one_way':one_way,'railroad_crossing':rail,
        'railroad_crossing_object_id':'701' if rail else None,
        'boundary_x_m':spec['boundary_x_m'],'native_map_sha256':geometry['native_map_sha256'],
        'original_frames':[row['native_frame'] for row in mapping],
        'road_directions_native':directions,'physical_observation_claimed':False,
        'legal_verdict':None,'synthetic_diagnostic':True}))
    (destination/'capture/manifest.json').write_text(json.dumps({
        'extraction_confirmed':True,'frames':frame_count,'synthetic_diagnostic':True}))
    camera_sizes={camera['name']:f"{camera['width']}x{camera['height']}" for camera in config['cameras']}
    for name in ('overview','approach','reference_corner','driver_reference'):
        size=camera_sizes[name] if full_resolution else '32x32'
        subprocess.run(['ffmpeg','-nostdin','-hide_banner','-loglevel','error','-y',
            '-f','lavfi','-i',f'color=c=black:s={size}:r=20:d={frame_count/20}',
            '-frames:v',str(frame_count),
            '-c:v','ffv1',str(destination/(name+'.mkv'))],check=True,timeout=30)
