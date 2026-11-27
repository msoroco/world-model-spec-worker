"""Independent diagnostic rail pair checks; no original or legal acceptance."""
import argparse
import hashlib
import json
import os
import shutil
import tempfile
from pathlib import Path
HERE=Path(__file__).resolve().parent
BRANCHES=('traffic_conflict','other_law','police_direction','official_device')
sha=lambda path:hashlib.sha256(Path(path).read_bytes()).hexdigest()
load=lambda path:json.loads(Path(path).read_text())
def lines(path):return [json.loads(x) for x in Path(path).read_text().splitlines()]
def inspect(comparison,source_root=HERE/'selected-source'):
    case_a,case_b=comparison['case_ids'];a,b=(case.split('__')[-1] for case in (case_a,case_b))
    branch=next((x for x in BRANCHES if a.startswith(x+'_')),None)
    if branch and b!=branch+'_2' or branch is None and ((a,b) not in (('condition_a','condition_b'),('stop_1','stop_2'),('stand_1','stand_2'))):
        raise ValueError('Comparison branch differs')
    roots=[source_root/a,source_root/b]
    surveys=[load(root/'original-rail-survey.json') for root in roots]
    if surveys[0]['rails']!=surveys[1]['rails'] or sha(roots[0]/'road.xodr')!=sha(roots[1]/'road.xodr'):
        raise ValueError('Fixed physical rail or road source differs')
    observations=[lines(root/'original-native-rows.jsonl') for root in roots]
    if any(len(rows)!=600 for rows in observations):raise ValueError('600 source frames required')
    for i in range(600):
        left,right=observations[0][i],observations[1][i]
        for key in ('vehicle_half_extent_xy_m','vehicle_yaw_rad','speed_mps'):
            if left[key]!=right[key]:raise ValueError('Fixed body extent, orientation or activity differs')
    cfg=[]
    for suffix in (a,b):
        construction=load(HERE/'native'/suffix/'construction.json')
        cfg.append(json.loads(next(x['content'] for x in construction['files'] if x['path']=='config.json')))
    for key in ('law_id','cell_id','actor','rate_hz','duration_frames','behavior_variant'):
        if cfg[0][key]!=cfg[1][key]:raise ValueError('Fixed selected construction changed: '+key)
    if branch:
        if cfg[0]['target_footprint_gap_m']!=cfg[1]['target_footprint_gap_m'] or cfg[0]['target_footprint_gap_m']!=12.5:
            raise ValueError('Exception comparison rail gap differs')
        if any(observations[0][i]['vehicle_center_xy_m']!=observations[1][i]['vehicle_center_xy_m'] for i in range(600)):
            raise ValueError('Exception comparison actor path differs')
        contexts=[load(root/'exception-context.json') for root in roots]
        if contexts[0]['branch']!=branch or contexts[1]['branch']!=branch or contexts[0]['requested_context_present'] is not False or contexts[1]['requested_context_present'] is not True:
            raise ValueError('Exact requested exception source did not change')
        changed='requested_'+branch+'_context'
    else:
        def rail_gap(row):
            return min(abs(row['vehicle_center_xy_m'][0]-rail['polyline_xy_m'][0][0])-row['vehicle_half_extent_xy_m'][0] for rail in surveys[0]['rails'])
        gaps=[rail_gap(rows[220]) for rows in observations]
        if gaps[0]>=15.24 or gaps[1]<=15.24:
            raise ValueError('Measured fixed-window rail-gap contrast absent')
        changed='measured_rail_gap_at_frame_220'
    return {'format':'c229398-rail-comparison-cpu-v1','comparison_id':comparison['comparison_id'],
            'case_ids':[case_a,case_b],'passed':True,
            'fixed_conditions_checked':['road_source','both_physical_rails','body_extent','activity','time_join','non_target_context'],
            'deliberate_difference_observed':changed,
            'source_sha256':{s:{name:sha(root/name) for name in ('road.xodr','original-native-rows.jsonl','original-rail-survey.json')} for s,root in ((a,roots[0]),(b,roots[1]))},
            'diagnostic_only':True,'original_native_observed':False,'legal_verdict':None}
def build():
    for comparison in load(HERE/'case-plan.json')['comparisons']:
        proof=inspect(comparison);target=HERE/'comparison-proof'/(comparison['comparison_id'].split('__')[-1]+'.json')
        target.parent.mkdir(exist_ok=True);target.write_text(json.dumps(proof,indent=2)+'\n')
        print(comparison['comparison_id'].split('__')[-1])
def negative():
    scratch=Path(os.environ['TMPDIR']).resolve()
    if '.runtime-work' not in scratch.parts:raise ValueError('Scratch must stay under .runtime-work')
    with tempfile.TemporaryDirectory(dir=scratch,prefix='c229398-comparison-negative-') as temporary:
        root=Path(temporary)
        for comparison in load(HERE/'case-plan.json')['comparisons']:
            names=[case.split('__')[-1] for case in comparison['case_ids']]
            for name in names:shutil.copytree(HERE/'selected-source'/name,root/name)
            (root/names[0]/'original-rail-survey.json').unlink()
            try:inspect(comparison,root)
            except (ValueError,FileNotFoundError):pass
            else:raise AssertionError('Comparison accepted missing rail survey')
            for name in names:shutil.rmtree(root/name)
            print(comparison['comparison_id'].split('__')[-1]+': missing rail source rejected')
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--build',action='store_true');p.add_argument('--negative',action='store_true');a=p.parse_args()
    if a.build:build()
    elif a.negative:negative()
    else:p.error('Use --build or --negative')
