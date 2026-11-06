"""Independent raw-row and exact-construction audit of passing fallback triggers."""
from __future__ import annotations
import hashlib
import json
import math
from pathlib import Path

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
OUT=ROOT/'.runtime-work/c102372-passing-engineering'
CASE=HERE.name+'__passing_overtake'


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def raw(name):
    root=OUT/name
    manifest=json.loads((root/'source-manifest.json').read_text())
    if manifest['format']!='c102372-passing-source-v1' or \
       set(manifest['sha256'])!={'native_samples.jsonl','following_context.json','road.xodr'}:
        raise ValueError('Passing source manifest differs')
    if any(sha(root/key)!=value for key,value in manifest['sha256'].items()):
        raise ValueError('Passing source changed')
    context=json.loads((root/'following_context.json').read_text())
    if context['case_id']!=CASE or context['source_kind']!='synthetic_cpu_fixture' or \
       context['passing_attempt'] is not True:
        raise ValueError('Passing source context differs')
    rows=[json.loads(line) for line in (root/'native_samples.jsonl').read_text().splitlines()]
    if len(rows)!=480:raise ValueError('Passing raw frame count differs')
    lanes=0;clearance=math.inf;offset=0
    for i,row in enumerate(rows):
        if row['native_frame']!=i or abs(row['time_s']-i/20)>.001 or \
           row['opposing_lane_actors']!=[]:
            raise ValueError('Passing raw frame identity differs')
        ego=row['ego'];lead=row['lead'];ep=ego['body_xy_m'];lp=lead['body_xy_m']
        ex=sum(p[0] for p in ep)/4;lx=sum(p[0] for p in lp)/4
        ey=sum(p[1] for p in ep)/4;ly=sum(p[1] for p in lp)/4
        if ego['lane_id']!=(1 if ey>=0 else -1) or lead['lane_id']!=-1:
            raise ValueError('Passing raw lane differs')
        lanes+=ego['lane_id']==1;offset=ex-lx
        clearance=min(clearance,math.hypot(max(0,abs(ex-lx)-12),
                                           max(0,abs(ey-ly)-2.6)))
    return {'final_center_offset_m':round(offset,4),
            'minimum_body_clearance_m':round(clearance,4),
            'opposing_lane_frames':lanes}


def audit():
    manifest=json.loads((HERE/'draft-execution-manifest.json').read_text())
    entry=next(item for item in manifest['cases'] if item['case_id']==CASE)
    names=('primary','fallback1','fallback2','fallback3')
    refs=[entry]+entry['candidates']
    constructions=[]
    for name,ref in zip(names,refs):
        path=HERE/ref['construction']
        if sha(path)!=ref['construction_sha256']:
            raise ValueError('Passing exact construction changed')
        value=json.loads(path.read_text())
        config=json.loads(next(item['content'] for item in value['files']
                               if item['path']=='config.json'))
        if config['case_id']!=CASE or config['candidate_id']!=name or \
           (config['law_id'],config['cell_id'],config['actor'])!=(
               'NRS-484B-127-2','C102372','heavy_vehicle_driver'):
            raise ValueError('Passing exact construction identity differs')
        constructions.append(value)
    if len({sha(HERE/ref['construction']) for ref in refs})!=4 or \
       {ref['trigger']['metric'] for ref in entry['candidates']}!={
           'final_center_offset_m','minimum_body_clearance_m','opposing_lane_frames'}:
        raise ValueError('Passing fallback construction/trigger diversity differs')
    values={name:raw(name) for name in names}
    values['underperforming']=raw('underperforming')
    if not (values['underperforming']['final_center_offset_m']<50<
            values['primary']['final_center_offset_m'] and
            values['primary']['minimum_body_clearance_m']<1.5<
            values['fallback2']['minimum_body_clearance_m'] and
            values['primary']['opposing_lane_frames']<300<
            values['fallback3']['opposing_lane_frames']):
        raise ValueError('Passing measured trigger boundaries not crossed')
    return {'passed':True,'case_id':CASE,'exact_candidates':4,
            'source_measured_metrics':values,'physical_or_selected_claim':False}


if __name__=='__main__':print(json.dumps(audit(),sort_keys=True))
