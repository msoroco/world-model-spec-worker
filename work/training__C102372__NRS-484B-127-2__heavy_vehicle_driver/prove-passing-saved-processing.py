"""Full 480-frame synthetic saved-processing proof for planned passing case."""
from __future__ import annotations
import importlib.util
import json
import os
from pathlib import Path
import shutil
import sys

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
OUT=ROOT/'.runtime-work/c102372-passing-saved'
sys.path.insert(0,str(HERE/'native'))
sys.path.insert(0,str(ROOT/'runtime/pipeline'))
sys.path.insert(0,str(ROOT/'runtime/pipeline/scenario_pipeline'))
from finalize import finalize
from measure_gap import sha
from passing_engineering import ASSIGNMENT,CASE
from passing_trigger import extract
from scenario_pipeline.worker_exchange.measurement_contract import verify_report

spec=importlib.util.spec_from_file_location('passing_fixture',HERE/'prove-passing-engineering.py')
fixture=importlib.util.module_from_spec(spec);spec.loader.exec_module(fixture)


def write_rows(path,rows):
    path.write_text(''.join(json.dumps(row,sort_keys=True,allow_nan=False)+'\n' for row in rows))


def make(root,source=None,case=None,trigger=None,source_format='c102372-passing-source-v1',
         measurement_channel='body_clearance_m'):
    source=source or fixture.write_case('primary')
    case=case or CASE
    trigger=trigger or extract
    if root.exists():shutil.rmtree(root)
    shutil.copytree(ROOT/'.runtime-work/c102372-saved-processing/probe_2-positive',root)
    for name in ('result.json','analysis-report.json'):
        (root/name).unlink(missing_ok=True)
    (root/'trigger-source-manifest.json').unlink(missing_ok=True)
    config=json.loads((root/'config.json').read_text())
    config['case_id']=ASSIGNMENT+'__'+case
    config['selected_case_id']=config['case_id']
    config['supported_case_ids']=[config['case_id']]
    config['case_suffix']=case
    channels=config['recording_description']['channels']
    for channel,name,unit,method in zip(channels,
        ('ego_body_pose','lead_body_pose',measurement_channel,'camera_frame_join'),
        ('structured','structured','m','structured'),
        ('Original Native subject body/pose/lane/velocity',
         'Separate original lead truck body/pose/lane/velocity',
         'Original truck body gap or clearance in the controlled sequence',
         'Original four-view video to Native frame join')):
        channel.update(name=name,unit=unit,method=method)
    (root/'config.json').write_text(json.dumps(config,indent=2)+'\n')
    original=[json.loads(line) for line in (source/'native_samples.jsonl').read_text().splitlines()]
    native=[json.loads(line) for line in (root/'native_samples.jsonl').read_text().splitlines()]
    trace=[json.loads(line) for line in (root/'trace.jsonl').read_text().splitlines()]
    evidence=[json.loads(line) for line in (root/'capture/evidence.jsonl').read_text().splitlines()]
    channels_data={key:[] for key in ('ego_body_pose','lead_body_pose',measurement_channel,'camera_frame_join')}
    joins=[json.loads(line) for line in (root/'video_frames.jsonl').read_text().splitlines()]
    for i,(base,shape,t,e,join) in enumerate(zip(native,original,trace,evidence,joins)):
        base['opposing_lane_actors']=[]
        if 'obstacle' in shape:base['obstacle']=shape['obstacle']
        for role in ('ego','lead'):
            actor=base[role];source_actor=shape[role];points=source_actor['body_xy_m']
            actor.update(body_xy_m=points,lane_id=source_actor['lane_id'],
                         speed_mps=source_actor['speed_mps'])
            center=[sum(p[j] for p in points)/4 for j in (0,1)]
            actor['center_xy_m']=center
            actor['body_vertices_m']=[[x,y,z] for x,y in points for z in (0,3)]
            actor['body_width_m']=max(p[1] for p in points)-min(p[1] for p in points)
        ego=base['ego'];lead=base['lead'];cx,cy=ego['center_xy_m']
        t['position_m']=[cx,cy,1.];t['position']={'x':cx,'y':cy,'z':1.}
        t['speed_mps']=ego['speed_mps'];t['speed_mph']=ego['speed_mps']/.44704
        e['ego']['body_vertices_m']=ego['body_vertices_m']
        e['ego']['position_m']=[cx,cy,1.]
        e['ego']['speed_mps']=ego['speed_mps']
        e['world']['road_projection']['lane_id']=ego['lane_id']
        e['world']['road_projection']['s_m']=cx
        eb=ego['body_xy_m'];lb=lead['body_xy_m']
        ex=sum(p[0] for p in eb)/4;lx=sum(p[0] for p in lb)/4
        ey=sum(p[1] for p in eb)/4;ly=sum(p[1] for p in lb)/4
        clearance=((max(0,abs(ex-lx)-12))**2+(max(0,abs(ey-ly)-2.6))**2)**.5
        values={'ego_body_pose':ego,'lead_body_pose':lead,
                measurement_channel:clearance,'camera_frame_join':join}
        for name,value in values.items():
            channels_data[name].append({'time_s':i/20,'value':value})
    write_rows(root/'native_samples.jsonl',native)
    write_rows(root/'trace.jsonl',trace)
    write_rows(root/'capture/evidence.jsonl',evidence)
    for name,rows in channels_data.items():write_rows(root/'channels'/(name+'.jsonl'),rows)
    for name in ('following_context.json','road.xodr','source-manifest.json'):
        shutil.copyfile(source/name,root/name)
    context=root/'following_context.json'
    context_value=json.loads(context.read_text())
    context_value['conditions_permit']={
        'source':'synthetic_cpu_assertion','status':'not_physically_verified'}
    context.write_text(json.dumps(context_value,sort_keys=True)+'\n')
    (root/'source-manifest.json').write_text(json.dumps({
        'format':source_format,'sha256':{name:sha(root/name)
        for name in ('native_samples.jsonl','following_context.json','road.xodr')}},sort_keys=True)+'\n')
    capture=json.loads((root/'capture/manifest.json').read_text())
    capture['sources']['native_samples.jsonl']=sha(root/'native_samples.jsonl')
    (root/'capture/manifest.json').write_text(json.dumps(capture,sort_keys=True)+'\n')
    (root/'fallback-metrics.json').write_text(json.dumps(trigger(root),sort_keys=True)+'\n')
    return config


def main():
    os.environ['PATH']=str(ROOT/'.runtime-work/linux_arm64')+os.pathsep+os.environ.get('PATH','')
    OUT.mkdir(parents=True,exist_ok=True)
    positive=OUT/'passing_overtake-positive';make(positive)
    negative=OUT/'passing_overtake-negative'
    if negative.exists():shutil.rmtree(negative)
    shutil.copytree(positive,negative)
    report=finalize(positive,positive/'analysis-report.json')
    contract=json.loads((HERE/'native/measurement-contract-passing_overtake.json').read_text())
    verify_report(contract,report,positive)
    result=json.loads((positive/'result.json').read_text())
    if not result['target_checks'][0]['matched'] or result['accepted']:
        raise ValueError('Passing saved target or acceptance differs')
    (negative/'native_samples.jsonl').unlink()
    try:finalize(negative,negative/'analysis-report.json')
    except ValueError as error:
        if 'Missing required source: native_samples.jsonl' not in str(error):raise
    else:raise AssertionError('Missing passing Native source accepted')
    return {'passed':True,'case_id':ASSIGNMENT+'__'+CASE,'frames':480,
            'video_frames':report['video_frames'],
            'minimum_body_clearance_m':result['measured_values']['truck_passing_sequence'][
                'minimum_body_clearance_m'],
            'source_sha256':sha(positive/'native_samples.jsonl'),
            'physical_or_accepted_claim':False}


if __name__=='__main__':print(json.dumps(main(),sort_keys=True))
