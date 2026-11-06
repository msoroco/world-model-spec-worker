"""480-frame synthetic positive and removed-source saved finalizer proof."""
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
OUT=ROOT/'.runtime-work/c102372-saved-processing'
sys.path.insert(0,str(HERE/'native'))
sys.path.insert(0,str(ROOT/'runtime/pipeline'))
sys.path.insert(0,str(ROOT/'runtime/pipeline/scenario_pipeline'))
from measure_gap import sha
from finalize import finalize
from scenario_pipeline.worker_exchange.measurement_contract import verify_report

spec=importlib.util.spec_from_file_location('synthetic',HERE/'prove-synthetic-gap.py')
synthetic=importlib.util.module_from_spec(spec);spec.loader.exec_module(synthetic)


def write_rows(path,rows):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(''.join(json.dumps(row,sort_keys=True,allow_nan=False)+'\n' for row in rows))


def augment(root,case):
    source=synthetic.write_case(case)
    if root.exists():shutil.rmtree(root)
    shutil.copytree(source,root)
    construction=json.loads((HERE/'draft-candidates'/case/'primary/construction.json').read_text())
    config=json.loads(next(item['content'] for item in construction['files']
                           if item['path']=='config.json'))
    (root/'config.json').write_text(json.dumps(config,indent=2)+'\n')
    native=[json.loads(line) for line in (root/'native_samples.jsonl').read_text().splitlines()]
    trace=[];evidence=[];mapping=[];channel_rows={
        name:[] for name in ('ego_body_pose','lead_body_pose','surface_gap_m','camera_frame_join')}
    for index,row in enumerate(native):
        frame=100+index;time=index/20
        row['carla_frame']=frame;row['elapsed_s']=time
        row['overview_camera_pose']={'xyz_m':[row['ego']['body_xy_m'][0][0]-10.,-2.,7.],
            'yaw_deg':0.,'pitch_deg':-12.}
        for key in ('ego','lead'):
            actor=row[key];points=actor['body_xy_m']
            actor['center_xy_m']=[sum(p[0] for p in points)/4,sum(p[1] for p in points)/4]
            actor['body_vertices_m']=[[x,y,z] for x,y in points for z in (0,3)]
            actor['body_width_m']=max(p[1] for p in points)-min(p[1] for p in points)
            actor['actor_id']=107 if key=='ego' else 108
            actor['blueprint_id']='synthetic_truck_geometry'
        trace.append({'frame':frame,'time_s':time,'position_m':row['ego']['center_xy_m']+[1.],
                      'position':{'x':row['ego']['center_xy_m'][0],
                                  'y':row['ego']['center_xy_m'][1],'z':1.},
                      'heading_deg':0,'speed_mps':row['ego']['speed_mps'],
                      'speed_mph':row['ego']['speed_mps']/.44704,
                      'control':{'throttle':0,'brake':0,'hand_brake':False}})
        evidence.append({'original_frame':frame,'recording_time_s':time,
            'replay_frame':frame,'replay_simulation_time_s':time,'actor_id':107,
            'synthetic_diagnostic':True,
            'ego':{'body_vertices_m':row['ego']['body_vertices_m'],
                   'position_m':row['ego']['center_xy_m']+[1.],
                   'heading_deg':0,'speed_mps':row['ego']['speed_mps'],
                   'speed_provenance':'original_trace_actor_get_velocity'},
            'world':{'weather':{'cloudiness':0,'precipitation':0,'wetness':0,'fog_density':0},
                     'road_projection':{'road_id':1,'section_id':0,'lane_id':-1,'s_m':row['ego']['center_xy_m'][0]}}})
        join={'video_frame':index,'native_frame':index,'carla_frame':frame,'time_s':time}
        mapping.append(join)
        gap=min(p[0] for p in row['lead']['body_xy_m'])-max(p[0] for p in row['ego']['body_xy_m'])
        values={'ego_body_pose':row['ego'],'lead_body_pose':row['lead'],
                'surface_gap_m':gap,'camera_frame_join':join}
        for name,value in values.items():channel_rows[name].append({'time_s':time,'value':value})
    write_rows(root/'native_samples.jsonl',native)
    context=json.loads((root/'following_context.json').read_text())
    context['conditions_permit']={'source':'synthetic_cpu_assertion',
                                  'status':'not_physically_verified'}
    (root/'following_context.json').write_text(json.dumps(context,sort_keys=True)+'\n')
    write_rows(root/'trace.jsonl',trace)
    write_rows(root/'capture/evidence.jsonl',evidence)
    write_rows(root/'video_frames.jsonl',mapping)
    for name,values in channel_rows.items():write_rows(root/'channels'/(name+'.jsonl'),values)
    synthetic.resign(root)
    (root/'capture/manifest.json').write_text(json.dumps({'frames':480,
        'extraction_confirmed':True,'synthetic_diagnostic':True,'sources':{
            'native_samples.jsonl':sha(root/'native_samples.jsonl')}},sort_keys=True)+'\n')
    ffmpeg=ROOT/'.runtime-work/linux_arm64/ffmpeg'
    for name in ('overview','ego_forward','lead_gap','crest_context'):
        subprocess.run([str(ffmpeg),'-nostdin','-hide_banner','-loglevel','error','-y',
            '-f','lavfi','-i','color=c=black:s=32x32:r=20:d=24','-frames:v','480',
            '-c:v','ffv1',str(root/(name+'.mkv'))],check=True,timeout=120)
    (root/'camera_context.json').write_text(json.dumps({'name':'overview',
        'width':32,'height':32,'fov_deg':90.,
        'source_kind':'synthetic_cpu_camera_emulation'},sort_keys=True)+'\n')
    from trigger_measure import SOURCES,extract
    (root/'trigger-source-manifest.json').write_text(json.dumps({
        'format':'c102372-truck-trigger-sources-v1',
        'sha256':{name:sha(root/name) for name in SOURCES}},sort_keys=True)+'\n')
    (root/'fallback-metrics.json').write_text(json.dumps(extract(root,case),sort_keys=True)+'\n')
    return config


def main():
    os.environ['PATH']=str(ROOT/'.runtime-work/linux_arm64')+os.pathsep+os.environ.get('PATH','')
    OUT.mkdir(parents=True,exist_ok=True)
    results={}
    for case in ('probe_1','probe_2'):
        positive=OUT/(case+'-positive')
        augment(positive,case)
        negative=OUT/(case+'-negative')
        if negative.exists():shutil.rmtree(negative)
        shutil.copytree(positive,negative)
        report=finalize(positive,positive/'analysis-report.json')
        contract=json.loads((HERE/'native'/('measurement-contract-'+case+'.json')).read_text())
        verify_report(contract,report,positive)
        result=json.loads((positive/'result.json').read_text())
        if not result['target_checks'][0]['matched'] or result['accepted']:
            raise ValueError('Synthetic truck target or acceptance differs')
        (negative/'native_samples.jsonl').unlink()
        try:finalize(negative,negative/'analysis-report.json')
        except ValueError as exc:
            if 'Missing required source: native_samples.jsonl' not in str(exc):raise
        else:raise AssertionError('Missing Native truck source accepted')
        results[case]={'relation':result['measured_values']['truck_following_gap']['relation_to_500ft'],
            'source_sha256':sha(positive/'native_samples.jsonl'),
            'four_video_frames':report['video_frames']}
    return {'passed':True,'cases':results,'physical_success_claimed':False,
            'accepted_recording_claimed':False}


if __name__=='__main__':print(json.dumps(main(),sort_keys=True))
