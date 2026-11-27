"""Independent fixed-condition and rolling-duration comparison audit."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
from analysis import sha
from delivery_audit import audit,required
from duration_measurement import maximum_rolling_hour

ROOT=Path(__file__).resolve().parent
FIXED_SOURCE_KEYS=('municipal_alley_source','engineer_designation_source','angle_marking_source',
                   'other_parking_rules_source','loading_activity_source','prior_vehicle_history_source','map_sha256')


def compare(comparison_id,attempts,diagnostic=False):
    plan=json.loads((ROOT/'case-plan.json').read_text())
    declared=next((r for r in plan['comparisons'] if r['comparison_id']==comparison_id),None)
    if declared is None:
        raise ValueError('unknown exact rolling-hour comparison')
    paths=[Path(path).resolve() for path in attempts]
    if len(paths)!=len(declared['case_ids']) or len(set(paths))!=len(paths):
        raise ValueError('comparison requires distinct exact captures for every selected case')
    reports=[audit(path,cid,diagnostic) for path,cid in zip(paths,declared['case_ids'])]
    cfg=[json.loads(required(path,'config.json').read_text()) for path in paths]
    ctx=[json.loads(required(path,'alley-context.json').read_text()) for path in paths]
    for key in ('law_id','cell_id','actor','rate_hz','duration_s','cameras'):
        if any(row.get(key)!=cfg[0].get(key) for row in cfg[1:]):
            raise ValueError('fixed capture condition differs: '+key)
    for key in FIXED_SOURCE_KEYS:
        if any(row.get(key)!=ctx[0].get(key) for row in ctx[1:]):
            raise ValueError('fixed original alley or other-lawfulness source differs: '+key)
    requested=[]
    measured=[]
    for case,config,report in zip(declared['case_ids'],cfg,reports):
        planned=next(item for item in plan['cases'] if item['case_id']==case)
        if config['case']['requested_intervals_s']!=planned['requested_parking_intervals_s']:
            raise ValueError('declared exact interval schedule changed')
        interval_records=[{'start_s':a,'end_s':b,'vehicle_id':'same-vehicle'} for a,b in config['case']['requested_intervals_s']]
        requested.append(maximum_rolling_hour(interval_records)['maximum_parked_seconds_in_any_hour'])
        value=report['measurement']
        if value['legal_classification']!='unreviewed':
            raise ValueError('legal classification must remain unreviewed')
        measured.append(value['maximum_parked_seconds_in_any_hour'])
    if requested!=sorted(requested) or len(set(requested))!=len(requested):
        raise ValueError('declared strict rolling-hour duration contrast absent')
    if not diagnostic:
        if any(abs(a-b)>5 for a,b in zip(measured,requested)):
            raise ValueError('original measured rolling-hour duration misses requested comparison target')
        if measured!=sorted(measured) or len(set(measured))!=len(measured):
            raise ValueError('original observed duration contrast absent')
    return {'format':'worker-alley-duration-comparison-audit','comparison_id':comparison_id,
            'case_ids':declared['case_ids'],'passed':True,'diagnostic_only':diagnostic,
            'physical_acceptance':False,'legal_acceptance':False,
            'fixed_conditions':declared['fixed_conditions'],
            'deliberate_differences':declared['deliberate_differences'],
            'requested_maximum_seconds':requested,'measured_maximum_seconds':measured,
            'source_sha256':[sha(path/'parking-history.jsonl') for path in paths]}


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--comparison',required=True)
    parser.add_argument('--attempt',type=Path,action='append',required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--diagnostic-fixture',action='store_true')
    args=parser.parse_args()
    result=compare(args.comparison,args.attempt,args.diagnostic_fixture)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({'comparison_id':args.comparison,'passed':True,'diagnostic_only':args.diagnostic_fixture}))


if __name__=='__main__':
    main()
