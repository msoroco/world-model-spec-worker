"""Independent raw-row and exact-construction audit of hold fallback triggers."""
from __future__ import annotations
import hashlib
import json
import math
from pathlib import Path

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
OUT=ROOT/'.runtime-work/c102372-passing-hold-engineering'
CASE=HERE.name+'__passing_hold'


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def raw(name):
    root=OUT/name
    manifest=json.loads((root/'source-manifest.json').read_text())
    if manifest['format']!='c102372-passing-source-v1' or \
       set(manifest['sha256'])!={'native_samples.jsonl','following_context.json','road.xodr'} or \
       any(sha(root/key)!=value for key,value in manifest['sha256'].items()):
        raise ValueError('Hold raw source changed')
    context=json.loads((root/'following_context.json').read_text())
    if context['case_id']!=CASE or context['source_kind']!='synthetic_cpu_fixture' or \
       context['passing_attempt'] is not False:
        raise ValueError('Hold source context differs')
    rows=[json.loads(line) for line in (root/'native_samples.jsonl').read_text().splitlines()]
    if len(rows)!=480:raise ValueError('Hold raw frame count differs')
    clearance=math.inf;speed_diff=0;lane_error=0
    for i,row in enumerate(rows):
        if row['native_frame']!=i or abs(row['time_s']-i/20)>.001 or \
           row['opposing_lane_actors']!=[]:
            raise ValueError('Hold frame identity differs')
        ego=row['ego'];lead=row['lead'];ep=ego['body_xy_m'];lp=lead['body_xy_m']
        ex=sum(p[0] for p in ep)/4;lx=sum(p[0] for p in lp)/4
        ey=sum(p[1] for p in ep)/4;ly=sum(p[1] for p in lp)/4
        if ego['lane_id']!=-1 or lead['lane_id']!=-1 or ex>=lx-12:
            raise ValueError('Hold lane/order differs')
        clearance=min(clearance,math.hypot(max(0,abs(ex-lx)-12),
                                           max(0,abs(ey-ly)-2.6)))
        speed_diff=max(speed_diff,abs(ego['speed_mps']-lead['speed_mps']))
        lane_error=max(lane_error,abs(ey+2))
    return {'minimum_body_clearance_m':round(clearance,4),
            'maximum_speed_difference_mps':round(speed_diff,4),
            'maximum_lane_center_error_m':round(lane_error,4)}


def audit():
    manifest=json.loads((HERE/'draft-execution-manifest.json').read_text())
    entry=next(item for item in manifest['cases'] if item['case_id']==CASE)
    names=('primary','fallback1','fallback2','fallback3')
    refs=[entry]+entry['candidates']
    for name,ref in zip(names,refs):
        path=HERE/ref['construction']
        if sha(path)!=ref['construction_sha256']:
            raise ValueError('Hold exact construction changed')
        value=json.loads(path.read_text())
        config=json.loads(next(item['content'] for item in value['files']
                               if item['path']=='config.json'))
        if config['case_id']!=CASE or config['candidate_id']!=name or \
           (config['law_id'],config['cell_id'],config['actor'])!=(
               'NRS-484B-127-2','C102372','heavy_vehicle_driver'):
            raise ValueError('Hold exact construction identity differs')
    if len({sha(HERE/ref['construction']) for ref in refs})!=4 or \
       {ref['trigger']['metric'] for ref in entry['candidates']}!={
           'minimum_body_clearance_m','maximum_speed_difference_mps',
           'maximum_lane_center_error_m'}:
        raise ValueError('Hold fallback diversity differs')
    values={name:raw(name) for name in (*names,'short_gap','speed_mismatch','lane_drift')}
    if not (values['short_gap']['minimum_body_clearance_m']<20<
            values['primary']['minimum_body_clearance_m'] and
            values['primary']['maximum_speed_difference_mps']<1<
            values['speed_mismatch']['maximum_speed_difference_mps'] and
            values['primary']['maximum_lane_center_error_m']<.3<
            values['lane_drift']['maximum_lane_center_error_m']):
        raise ValueError('Hold measured threshold not crossed')
    return {'passed':True,'case_id':CASE,'exact_candidates':4,
            'source_measured_metrics':values,'physical_or_selected_claim':False}


if __name__=='__main__':print(json.dumps(audit(),sort_keys=True))
