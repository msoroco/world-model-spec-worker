"""Generate source-shaped synthetic overpass diagnostics for software proofs."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from overpass_source import CASES, FRAMES, sha

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
CAMERAS = ('overview','approach','reference_corner','driver_reference')


def lines(items):
    return ''.join(json.dumps(item, separators=(',',':'),allow_nan=False)+'\n' for item in items)


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value,separators=(',',':'),allow_nan=False)+'\n')


def build(variant):
    case_id = ROOT.name+'__'+variant
    scene_path = ROOT/('scene-'+variant+'.json')
    scene = json.loads(scene_path.read_text())
    body, trace, frames, evidence, native, graphs = [], [], [], [], [], []
    for i in range(FRAMES):
        t = round(i*.05,6)
        vehicle_x = -30+5*t
        walker_t = max(0,t-(7.2 if variant=='yield_before_vehicle' else 0))
        walker_y = min(8.0,-8+1.4*walker_t)
        frame = 1000+i
        vehicle = {'actor_id':22,'xyz_m':[vehicle_x,-1.75,.3],
                   'velocity_xyz_mps':[5.0,0.0,0.0]}
        body.append({'case_id':case_id,'frame':frame,'time_s':t,
                     'pedestrian_actor_id':11,'vehicle_actor_id':22,
                     'pedestrian_xyz_m':[0.0,walker_y,.2],
                     'vehicle_xyz_m':vehicle['xyz_m'],
                     'vehicle_velocity_xyz_mps':vehicle['velocity_xyz_mps'],
                     'all_native_vehicles':[vehicle]})
        trace.append({'frame':frame,'time_s':t,'actor_id':11,
                      'position_m':[0.0,walker_y,.2],
                      'position':{'x':0.0,'y':walker_y,'z':.2},
                      'heading_deg':90,'speed_mps':0 if t < 7.2 and variant=='yield_before_vehicle' else 1.4,
                      'speed_mph':0 if t < 7.2 and variant=='yield_before_vehicle' else 1.4/.44704,
                      'velocity_mps':[0.0,1.4,0.0],'control':{}})
        frames.append({'video_frame':i,'carla_frame':frame,
                       'native_frame':frame,'time_s':t})
        observation={'frame':frame,'time_s':t,'map_context':{},'participants':[]}
        evidence.append({'actor_id':11,'original_frame':frame,
                         'recording_time_s':t,'replay_frame':frame,
                         'replay_simulation_time_s':t,
                         'ego':{'position_m':[0.0,walker_y,.2],
                                'speed_mps':trace[-1]['speed_mps'],
                                'speed_provenance':'synthetic_native_sample'},
                         'original_observations':observation,'world':{'weather':{}}})
        native.append({'adapter_graph':f'graphs/base/{frame:08d}.adapter.json',
                       'frame':frame,'simulation_time':t})
        graphs.append({'path':f'capture/native/graphs/base/{frame:08d}.adapter.json',
                       'attributes':{'frame':frame,'time_s':t,
                                     'observed_evidence':observation},
                       'nodes':[],'edges':[]})
    site_text='Synthetic overpass review fixture; no original structure verified.\n'
    municipal_text='Synthetic municipal designation fixture; no local legal finding.\n'
    packet={'format':'c188132-reviewed-overpass-site-v1',
            'provenance_kind':'synthetic_fixture','case_id':case_id,
            'map_sha256':sha(ROOT/'candidate-overpass.xodr'),
            'crossing_point_xy_m':scene['crossing_point_xy_m'],
            'surface_road_id':1,'deck_road_id':2,
            'roadway_y_bounds_m':[-3.5,3.5],
            'provided_overhead_crossing':True,'usable_deck_access':True,
            'independent_review':{'reviewer':'synthetic software fixture',
                                  'source':'reviewed-site-source.txt',
                                  'sha256':digest(site_text)},
            'municipal_designation':{'prohibited':scene['designated_prohibition'],
                                     'source':'municipal-designation-source.txt',
                                     'sha256':digest(municipal_text)}}
    files={'body-history.jsonl':lines(body),'trace.jsonl':lines(trace),
           'video_frames.jsonl':lines(frames),
           'capture/evidence.jsonl':lines(evidence),
           'capture/native/frames.jsonl':lines(native),
           'capture/recorder_info.txt':'Create 11: walker.pedestrian (synthetic diagnostic)\n',
           'reviewed-site-source.txt':site_text,
           'municipal-designation-source.txt':municipal_text,
           'reviewed-site.json':json.dumps(packet,separators=(',',':'))+'\n',
           'acquisition-provenance.json':json.dumps({'diagnostic_fixture':True,
                    'provenance_kind':'synthetic_fixture','scope':'software-only'},
                    separators=(',',':'))+'\n'}
    source_files={'scene':('scene.json',sha(scene_path)),
                  'map':('candidate-overpass.xodr',sha(ROOT/'candidate-overpass.xodr')),
                  'body_history':('body-history.jsonl',digest(files['body-history.jsonl'])),
                  'frame_map':('video_frames.jsonl',digest(files['video_frames.jsonl'])),
                  'site_review':('reviewed-site.json',digest(files['reviewed-site.json'])),
                  'site_review_source':('reviewed-site-source.txt',digest(site_text)),
                  'municipal_source':('municipal-designation-source.txt',digest(municipal_text))}
    manifest={'format':'c188132-original-sources-v1'}
    manifest.update({key:{'path':name,'sha256':checksum}
                     for key,(name,checksum) in source_files.items()})
    files['source-manifest.json']=json.dumps(manifest,separators=(',',':'))+'\n'
    files['capture/manifest.json']=json.dumps({'acquisition':'original_live_run',
        'case_id':case_id,'complete_driving_lanes':False,
        'extraction_confirmed':True,'frames':FRAMES,
        'sources':{'candidate-overpass.xodr':sha(ROOT/'candidate-overpass.xodr'),
                   'trace.jsonl':digest(files['trace.jsonl'])},'status':'draft'},
        separators=(',',':'))+'\n'
    videos=[{'path':name+'.mkv','frames':FRAMES,
             'width':1920 if name=='overview' else 1280,
             'height':1080 if name=='overview' else 720,
             'fps':20,'color':'black'} for name in CAMERAS]
    spec={'files':files,'graphs':graphs,'videos':videos}
    spec_path=ROOT/('diagnostic-'+variant+'.json')
    write(spec_path,spec)
    note_path=ROOT/('diagnostic-source-note-'+variant+'.json')
    write(note_path,{'case_id':case_id,'provenance_kind':'synthetic_fixture',
                     'purpose':'software compatibility only',
                     'physical_crossing_and_deck':'unverified'})
    recipe={'format':'worker-fixture-recipe',
            'sources':[{'path':note_path.name,
                        'source':str(note_path.relative_to(REPO)),
                        'sha256':sha(note_path)}],
            'generator':{'source':str(spec_path.relative_to(REPO)),
                         'sha256':sha(spec_path)}}
    recipe_path=ROOT/('fixture-recipe-'+variant+'.json')
    write(recipe_path,recipe)
    return {'variant':variant,'spec_bytes':spec_path.stat().st_size,
            'recipe':str(recipe_path.relative_to(REPO))}


if __name__=='__main__':
    print(json.dumps([build(variant) for variant in CASES]))
