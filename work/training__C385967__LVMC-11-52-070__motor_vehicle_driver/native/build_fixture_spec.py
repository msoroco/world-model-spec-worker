"""Inventory bounded synthetic original-shaped sources for CPU compatibility."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from prove_saved_sources import FOLDER, HERE, ROOT, source, sha


def lines(rows):
    return ''.join(json.dumps(row,separators=(',',':'),allow_nan=False)+'\n' for row in rows)


def create(suffix):
    if suffix not in ('a','b'): raise ValueError('Unknown case')
    yaw=45 if suffix=='a' else 225
    case=FOLDER.name+'__probe_'+suffix
    folder=source(case,yaw)
    names=('permission-source.bin','permission_authority.json',
           'road_geometry.json','parking_context.json','native_samples.jsonl',
           'video_frames.jsonl','body_history.jsonl')
    files={name:(folder/name).read_text() for name in names}
    files['road.xodr']=(HERE/'angle-bay-road.xodr').read_text()
    samples=[json.loads(x) for x in files['native_samples.jsonl'].splitlines()]
    traces=[];evidence=[];frames=[];graphs=[]
    for row in samples:
        frame=row['native_frame'];time_s=row['time_s'];index=row['frame']
        traces.append({'frame':frame,'time_s':time_s,
            'position':{'x':6.5,'y':0,'z':.5},'position_m':[6.5,0,.5],
            'heading_deg':yaw,'speed_mps':0,'speed_mph':0,
            'velocity_mps':[0,0,0],
            'control':{'throttle':0,'brake':1,'hand_brake':True}})
        evidence.append({'original_frame':frame,'recording_time_s':time_s,
            'replay_frame':frame,'replay_simulation_time_s':time_s,'actor_id':17,
            'ego':{'position_m':[6.5,0,.5], 'heading_deg':yaw,'speed_mps':0,
                'body_vertices_m':[[6.5+dx,dy,.5] for dx,dy in
                  ((-.7,-.4),(-.7,.4),(.7,.4),(.7,-.4))],
                'speed_provenance':'synthetic_native_sample',
                'synthetic_diagnostic':True},
            'world':{'weather':{'cloudiness':0,'precipitation':0,'wetness':0,'fog_density':0},
                'road_projection':{'road_id':1,'section_id':0,'lane_id':-2,'s_m':70}}})
        graph_rel=f'graphs/base/{frame:08d}.adapter.json'
        frames.append({'frame':frame,'simulation_time':time_s,'time_s':time_s,
            'base':graph_rel,'adapter_graph':graph_rel,'synthetic_diagnostic':True})
        graphs.append({'path':'capture/native/'+graph_rel,
            'attributes':{'frame':frame},'nodes':[],'edges':[]})
    files['trace.jsonl']=lines(traces)
    files['capture/evidence.jsonl']=lines(evidence)
    files['capture/native/frames.jsonl']=lines(frames)
    files['capture/recorder_info.txt']='Create 17: vehicle.lincoln.mkz_2020\n'
    files['capture/manifest.json']=json.dumps({'extraction_confirmed':True,
        'frames':600,'synthetic_diagnostic':True,
        'sources':{'road.xodr':hashlib.sha256(files['road.xodr'].encode()).hexdigest(),
                   'trace.jsonl':hashlib.sha256(files['trace.jsonl'].encode()).hexdigest()}},
        separators=(',',':'))+'\n'
    videos=[{'path':name+'.mkv','frames':600,'width':width,'height':height,
        'fps':20,'color':'blue'} for name,width,height in
        (('overview',1920,1080),('approach',1280,720),
         ('reference_corner',1280,720),('driver_reference',1280,720))]
    spec=HERE/f'selected-{suffix}-fixture.json'
    spec.write_text(json.dumps({'files':files,'graphs':graphs,'videos':videos},
        separators=(',',':'),allow_nan=False)+'\n')
    source_path=ROOT/'inputs'/FOLDER.name/'assignment.json'
    recipe=HERE/f'selected-{suffix}-fixture-recipe.json'
    recipe.write_text(json.dumps({'format':'worker-fixture-recipe',
        'sources':[{'path':'diagnostic-input-assignment.json',
                    'source':str(source_path.relative_to(ROOT)),'sha256':sha(source_path)}],
        'generator':{'source':str(spec.relative_to(ROOT)),'sha256':sha(spec)}},
        indent=2)+'\n')
    if spec.stat().st_size>2*1024*1024:
        raise ValueError('Fixture spec too large for returned file')
    return {'case_id':case,'spec_bytes':spec.stat().st_size,
            'spec_sha256':sha(spec),'recipe_sha256':sha(recipe)}


if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--condition',choices=('a','b'),required=True)
    a=p.parse_args()
    print(json.dumps(create(a.condition),sort_keys=True))
