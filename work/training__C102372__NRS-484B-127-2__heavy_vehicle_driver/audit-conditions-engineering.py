"""Independent source-row and exact-bundle audit of six conditions triggers."""
from __future__ import annotations
import hashlib
import json
import math
from pathlib import Path
import xml.etree.ElementTree as ET

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
OUT=ROOT/'.runtime-work/c102372-conditions-engineering'
CASES=('conditions_steady','conditions_lead_brake')
CANDIDATES=('primary','fallback1','fallback2','fallback3')


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def arc_gap(row,profile):
    x0=max(x for x,_ in row['ego']['body_xy_m']);x1=min(x for x,_ in row['lead']['body_xy_m'])
    n=math.ceil((x1-x0)/.1);step=(x1-x0)/n;total=0
    for i in range(n):
        x=x0+(i+.5)*step
        p=max((v for v in profile if float(v.get('s'))<=x),key=lambda v:float(v.get('s')))
        u=x-float(p.get('s'))
        slope=float(p.get('b'))+2*float(p.get('c'))*u+3*float(p.get('d'))*u*u
        total+=math.hypot(1,slope)*step
    return total


def raw(case,name):
    root=OUT/(case+'-'+name)
    manifest=json.loads((root/'source-manifest.json').read_text())
    if manifest['format']!='c102372-conditions-source-v1' or \
       set(manifest['sha256'])!={'native_samples.jsonl','following_context.json','road.xodr'} or \
       any(sha(root/key)!=value for key,value in manifest['sha256'].items()):
        raise ValueError('Conditions trigger source changed')
    context=json.loads((root/'following_context.json').read_text())
    if context.get('case_id')!=HERE.name+'__'+case or \
       context['source_kind']!='synthetic_cpu_fixture':
        raise ValueError('Conditions trigger context differs')
    rows=[json.loads(line) for line in (root/'native_samples.jsonl').read_text().splitlines()]
    if len(rows)!=480:raise ValueError('Conditions trigger frame count differs')
    profile=ET.parse(root/'road.xodr').getroot().find('road').findall('elevationProfile/elevation')
    gaps=[];speed=0;obstacle=math.inf
    for i,row in enumerate(rows):
        if row['native_frame']!=i or abs(row['time_s']-i/20)>.001:
            raise ValueError('Conditions trigger frame identity differs')
        gaps.append(arc_gap(row,profile))
        speed=max(speed,abs(row['ego']['speed_mps']-row['lead']['speed_mps']))
        if row['obstacle'] is not None:
            obstacle=min(obstacle,min(x for x,_ in row['obstacle']['body_xy_m'])-
                         max(x for x,_ in row['lead']['body_xy_m']))
    return {'minimum_surface_gap_m':round(min(gaps),4),
            'surface_gap_compression_m':round(gaps[0]-min(gaps),4),
            'maximum_speed_difference_mps':round(speed,4),
            'minimum_lead_obstacle_clearance_m':round(obstacle,4)
                    if obstacle<math.inf else None}


def audit():
    manifest=json.loads((HERE/'draft-execution-manifest.json').read_text())
    values={}
    for case in CASES:
        entry=next(item for item in manifest['cases'] if item['case_id']==HERE.name+'__'+case)
        refs=[entry]+entry['candidates']
        for candidate,ref in zip(CANDIDATES,refs):
            path=HERE/ref['construction'];value=json.loads(path.read_text())
            if sha(path)!=ref['construction_sha256']:
                raise ValueError('Conditions exact construction changed')
            config=json.loads(next(item['content'] for item in value['files']
                                   if item['path']=='config.json'))
            if config['case_id']!=entry['case_id'] or config['candidate_id']!=candidate or \
               (config['law_id'],config['cell_id'],config['actor'])!=(
                   'NRS-484B-127-2','C102372','heavy_vehicle_driver'):
                raise ValueError('Conditions exact candidate identity differs')
        if len({sha(HERE/ref['construction']) for ref in refs})!=4 or \
           len({ref['trigger']['metric'] for ref in entry['candidates']})!=3:
            raise ValueError('Conditions candidate/trigger diversity differs')
        values[case]={name:raw(case,name) for name in (*CANDIDATES,
                    *(('gap_compress','speed_mismatch') if case==CASES[0] else ()))}
    s=values[CASES[0]];e=values[CASES[1]]
    if not (s['primary']['minimum_surface_gap_m']<160<=s['fallback1']['minimum_surface_gap_m'] and
            s['primary']['surface_gap_compression_m']<1<s['gap_compress']['surface_gap_compression_m'] and
            s['primary']['maximum_speed_difference_mps']<1<s['speed_mismatch']['maximum_speed_difference_mps'] and
            e['primary']['minimum_surface_gap_m']<142<e['fallback1']['minimum_surface_gap_m'] and
            e['fallback2']['surface_gap_compression_m']<15<e['primary']['surface_gap_compression_m'] and
            e['primary']['minimum_lead_obstacle_clearance_m']<20<
            e['fallback3']['minimum_lead_obstacle_clearance_m']):
        raise ValueError('Conditions raw measured thresholds not crossed')
    return {'passed':True,'exact_candidates':8,'source_measured_metrics':values,
            'physical_or_selected_claim':False}


if __name__=='__main__':print(json.dumps(audit(),sort_keys=True))
