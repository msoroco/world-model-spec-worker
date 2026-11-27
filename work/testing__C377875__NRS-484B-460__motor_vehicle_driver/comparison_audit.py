"""Independent source-bound paired body-angle comparison; no legal threshold."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
from analysis import measure_saved, sha
from delivery_audit import audit, required

ROOT=Path(__file__).resolve().parent

def compare(comparison_id, first, second, diagnostic=False):
    plan=json.loads((ROOT/'case-plan.json').read_text())
    row=next((r for r in plan['comparisons'] if r['comparison_id']==comparison_id),None)
    if row is None:raise ValueError('unknown exact angle comparison')
    first,second=Path(first).resolve(),Path(second).resolve()
    if first==second:raise ValueError('comparison requires distinct captures')
    attempts=[first,second]
    reports=[audit(path,cid,diagnostic) for path,cid in zip(attempts,row['case_ids'])]
    cfg=[json.loads(required(path,'config.json').read_text()) for path in attempts]
    ctx=[json.loads(required(path,'angle-context.json').read_text()) for path in attempts]
    for key in ('law_id','cell_id','actor','rate_hz','duration_s','cameras'):
        if cfg[0].get(key)!=cfg[1].get(key):raise ValueError('fixed capture condition differs: '+key)
    for key in ('indicated_angle_degrees','curb_edge_xy','requested_activity'):
        if ctx[0].get(key)!=ctx[1].get(key):raise ValueError('fixed source context differs: '+key)
    for key in ('requested_orientation',):
        if [c.get(key) for c in ctx]!=['indicated','offset']:
            raise ValueError('declared body-angle contrast missing')
    measures=[report['measurement'] for report in reports]
    angles=[m['body_to_curb_angle_mean_degrees'] for m in measures]
    if abs(angles[0]-angles[1])<1.0:
        raise ValueError('observed body-angle contrast absent')
    for packet in measures:
        if packet['legal_classification']!='unreviewed':raise ValueError('unexpected legal classification')
    return {'format':'worker-angle-comparison-audit','comparison_id':comparison_id,
            'case_ids':row['case_ids'],'passed':True,'diagnostic_only':diagnostic,
            'physical_acceptance':False,'legal_acceptance':False,
            'fixed_conditions':row['fixed_conditions'],
            'deliberate_differences':row['deliberate_differences'],
            'observed_body_to_curb_degrees':angles,
            'source_sha256':[sha(path/'angle-history.jsonl') for path in attempts]}

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--comparison',required=True)
    p.add_argument('--first-attempt',type=Path,required=True)
    p.add_argument('--second-attempt',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--diagnostic-fixture',action='store_true')
    a=p.parse_args()
    result=compare(a.comparison,a.first_attempt,a.second_attempt,a.diagnostic_fixture)
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({'comparison_id':a.comparison,'passed':True,'diagnostic_only':a.diagnostic_fixture}))
if __name__=='__main__':main()
