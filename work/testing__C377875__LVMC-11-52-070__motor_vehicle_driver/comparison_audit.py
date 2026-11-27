"""Independent source-bound Engineer-angle-parking front-direction pair audit."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
from analysis import sha
from delivery_audit import audit,required
ROOT=Path(__file__).resolve().parent

def compare(comparison_id,first,second,diagnostic=False):
    plan=json.loads((ROOT/'case-plan.json').read_text())
    declared=next((r for r in plan['comparisons'] if r['comparison_id']==comparison_id),None)
    if declared is None:raise ValueError('unknown exact orientation comparison')
    first,second=Path(first).resolve(),Path(second).resolve()
    if first==second:raise ValueError('comparison requires distinct exact captures')
    reports=[audit(path,cid,diagnostic) for path,cid in zip((first,second),declared['case_ids'])]
    cfg=[json.loads(required(path,'config.json').read_text()) for path in (first,second)]
    ctx=[json.loads(required(path,'orientation-context.json').read_text()) for path in (first,second)]
    for key in ('law_id','cell_id','actor','rate_hz','duration_s','cameras'):
        if cfg[0].get(key)!=cfg[1].get(key):raise ValueError('fixed capture condition differs: '+key)
    for key in ('lawful_traffic_vector_xy','lawful_direction_status','requested_activity'):
        if ctx[0].get(key)!=ctx[1].get(key):raise ValueError('fixed original context differs: '+key)
    if [c.get('requested_orientation') for c in ctx]!=['forward','opposing']:
        raise ValueError('declared front-direction contrast absent')
    angles=[r['measurement']['front_vs_lawful_direction_mean_degrees'] for r in reports]
    if angles[0]>45 or angles[1]<135:raise ValueError('observed diagnostic front-direction contrast absent')
    if any(r['measurement']['legal_classification']!='unreviewed' for r in reports):
        raise ValueError('legal classification must remain unreviewed')
    return {'format':'worker-engineer-angle-comparison-audit','comparison_id':comparison_id,
            'case_ids':declared['case_ids'],'passed':True,'diagnostic_only':diagnostic,
            'physical_acceptance':False,'legal_acceptance':False,
            'fixed_conditions':declared['fixed_conditions'],
            'deliberate_differences':declared['deliberate_differences'],
            'front_vs_lawful_direction_degrees':angles,
            'source_sha256':[sha(path/'orientation-history.jsonl') for path in (first,second)]}

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--comparison',required=True);p.add_argument('--first-attempt',type=Path,required=True)
    p.add_argument('--second-attempt',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--diagnostic-fixture',action='store_true');a=p.parse_args()
    result=compare(a.comparison,a.first_attempt,a.second_attempt,a.diagnostic_fixture)
    a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({'comparison_id':a.comparison,'passed':True,'diagnostic_only':a.diagnostic_fixture}))
if __name__=='__main__':main()
