"""Independently audit five fixed-condition truck-route contrasts."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from delivery_audit import audit,required,sha

ROOT=Path(__file__).resolve().parent
CONTRASTS={'pickup_required_vs_through':('pick_up','none'),'delivery_required_vs_through':('delivery','none'),
    'essential_required_vs_through':('essential_use','none'),'local_non_through_vs_through':('local','through'),
    'designated_route_vs_through':('truck_route','non_truck')}


def compare(comparison_id:str,first:Path,second:Path,diagnostic:bool=False)->dict:
    plan=json.loads((ROOT/'case-plan.json').read_text())
    declared=next((row for row in plan['comparisons'] if row['comparison_id']==comparison_id),None)
    if declared is None or comparison_id not in CONTRASTS:raise ValueError('Unknown exact truck-route comparison')
    attempts=[first.resolve(),second.resolve()]
    reports=[];packets=[];configs=[];specs=[]
    for attempt,case_id in zip(attempts,declared['case_ids']):
        reports.append(audit(attempt,case_id,diagnostic))
        packets.append(json.loads(required(attempt,'original-route-observations.json').read_text()))
        configs.append(json.loads(required(attempt,'config.json').read_text()))
        specs.append(json.loads(required(attempt,'case-spec.json').read_text()))
    for key in ('law_id','cell_id','actor','rate_hz','duration_s','cameras'):
        if configs[0].get(key)!=configs[1].get(key):raise ValueError('Fixed capture condition differs: '+key)
    left,right=packets
    if left.get('assignment_id')!=right.get('assignment_id'):
        raise ValueError('Fixed assignment differs')
    for key in ('municipal_jurisdiction_reviewed','chapter_scope_reviewed','governing_controls_reviewed','truck_routes'):
        if left['site'].get(key)!=right['site'].get(key):raise ValueError('Fixed route context differs: '+key)
    kind=comparison_id.split('_vs_through')[0]
    if kind in ('pickup_required','delivery_required','essential_required'):
        if (specs[0]['street_class'],specs[0]['route_use'])!=(specs[1]['street_class'],specs[1]['route_use']):
            raise ValueError('Purpose contrast changed route class or passage')
        if tuple(spec['enroute_purpose'] for spec in specs)!=CONTRASTS[comparison_id]:
            raise ValueError('Required-enroute purpose contrast absent')
        if left['site']['intervening_street']!=right['site']['intervening_street']:
            raise ValueError('Purpose contrast changed connecting street')
        if [row['road_id'] for row in left['frames']]!=[row['road_id'] for row in right['frames']]:
            raise ValueError('Purpose contrast changed road path')
    elif kind=='local_non_through':
        if tuple(spec['route_use'] for spec in specs)!=CONTRASTS[comparison_id]:
            raise ValueError('Through versus local route contrast absent')
        if (specs[0]['street_class'],specs[0]['enroute_purpose'])!=(specs[1]['street_class'],specs[1]['enroute_purpose']):
            raise ValueError('Local contrast changed street or purpose')
        if left['site']['intervening_street']!=right['site']['intervening_street']:
            raise ValueError('Local contrast changed connector designation')
        if [row['road_id'] for row in left['frames']]==[row['road_id'] for row in right['frames']]:
            raise ValueError('Local contrast did not change original endpoint')
    else:
        if tuple(spec['street_class'] for spec in specs)!=CONTRASTS[comparison_id]:
            raise ValueError('Designated-route contrast absent')
        if (specs[0]['route_use'],specs[0]['enroute_purpose'])!=(specs[1]['route_use'],specs[1]['enroute_purpose']):
            raise ValueError('Designation contrast changed route use or purpose')
        if [row['road_id'] for row in left['frames']]!=[row['road_id'] for row in right['frames']]:
            raise ValueError('Designation contrast changed road path')
        if left['site']['intervening_street']['designation']==right['site']['intervening_street']['designation']:
            raise ValueError('Designation contrast did not change source status')
    if sha(attempts[0]/'original-route-observations.json')==sha(attempts[1]/'original-route-observations.json'):
        raise ValueError('Comparison reused one original route source')
    return {'format':'worker-comparison-audit','comparison_id':comparison_id,'case_ids':declared['case_ids'],
        'passed':True,'diagnostic_only':diagnostic,'physical_acceptance':False,'legal_acceptance':False,
        'fixed_conditions':declared['fixed_conditions'],'deliberate_differences':declared['deliberate_differences'],
        'source_sha256':[sha(attempt/'original-route-observations.json') for attempt in attempts],
        'frame_counts':[report['frame_count'] for report in reports]}


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--comparison',required=True);parser.add_argument('--first-attempt',type=Path,required=True);parser.add_argument('--second-attempt',type=Path,required=True);parser.add_argument('--output',type=Path,required=True);parser.add_argument('--diagnostic-fixture',action='store_true');args=parser.parse_args()
    for source in (args.first_attempt,args.second_attempt):
        if args.output.resolve()==source.resolve() or source.resolve() in args.output.resolve().parents:
            raise ValueError('Comparison report must be outside original attempt')
    result=compare(args.comparison,args.first_attempt,args.second_attempt,args.diagnostic_fixture)
    if args.output.exists():raise ValueError('Retain prior comparison report')
    args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
    print(json.dumps({'comparison_id':args.comparison,'passed':True,'diagnostic_only':args.diagnostic_fixture}))

if __name__=='__main__':main()
