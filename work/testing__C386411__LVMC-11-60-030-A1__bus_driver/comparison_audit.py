"""Independent bus-stop comparisons from source-bound saved analysis reports."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parent
AID=ROOT.name


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def audit_comparison(comparison, reports, *, diagnostic=False):
    ids=comparison['case_ids']
    if len(ids)!=2 or set(reports)!=set(ids):
        raise ValueError('exact comparison cases missing')
    samples=[]
    for case_id in ids:
        report=reports[case_id]
        if report.get('case_id')!=case_id or report.get('legal_verdict') is not None:
            raise ValueError('wrong analysis case or legal verdict')
        observation=report.get('observation',{})
        if observation.get('diagnostic_only') is not diagnostic:
            raise ValueError('original versus diagnostic source status differs')
        conduct,relation=case_id.removeprefix(AID+'__').split('_')
        if observation.get('conduct')!=conduct or observation.get('location_relation')!=relation:
            raise ValueError('observed conduct or stop boundary differs from selected probe')
        refs=observation.get('source_refs',{})
        if not {'site','designation','identity','activity','native'}<=set(refs):
            raise ValueError('source-bound comparison observations incomplete')
        samples.append((conduct,relation,refs,observation))
    first,second=samples
    for key in ('site','designation','identity'):
        if first[2][key]['sha256']!=second[2][key]['sha256']:
            raise ValueError('fixed reviewed site, designation or bus identity changed: '+key)
    if first[3].get('observed_duration_s')!=second[3].get('observed_duration_s'):
        raise ValueError('fixed stopped interval duration changed')
    differences=comparison.get('deliberate_differences',[])
    if comparison['comparison_id'].endswith('stop_boundary'):
        if (first[0],second[0]) not in (('stand','stand'),('park','park')) or {first[1],second[1]}!={'inside','outside'}:
            raise ValueError('stop boundary contrast collapsed')
    elif comparison['comparison_id']=='stand_versus_park_inside':
        if {first[0],second[0]}!={'stand','park'} or first[1]!='inside' or second[1]!='inside':
            raise ValueError('standing versus parking contrast collapsed')
    else:
        raise ValueError('unknown bus-stop comparison')
    if not differences or not comparison.get('fixed_conditions'):
        raise ValueError('comparison conditions missing')
    return {'format':'worker-bus-stop-comparison-audit','comparison_id':comparison['comparison_id'],
            'case_ids':ids,'passed':True,'diagnostic_only':diagnostic,
            'fixed_source_sha256':{key:first[2][key]['sha256'] for key in ('site','designation','identity')},
            'deliberate_differences':differences,'legal_verdict':None}


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--comparison',required=True)
    parser.add_argument('--attempts',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    plan=json.loads((ROOT/'case-plan.json').read_text())
    comparison=next((x for x in plan['comparisons'] if x['comparison_id']==args.comparison),None)
    if comparison is None:raise ValueError('unknown comparison ID')
    attempts=json.loads(args.attempts.read_text())
    reports={}
    for case_id in comparison['case_ids']:
        folder=Path(attempts[case_id]).resolve()
        path=folder/'analysis-report.json'
        if not path.is_file():raise ValueError('original analysis report missing: '+case_id)
        reports[case_id]=json.loads(path.read_text())
    receipt=audit_comparison(comparison,reports,diagnostic=False)
    if args.output.exists():raise ValueError('retain prior independent comparison receipt')
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(receipt,indent=2,sort_keys=True)+'\n')
    print('original source-bound comparison audited: '+args.comparison)


if __name__=='__main__':main()
