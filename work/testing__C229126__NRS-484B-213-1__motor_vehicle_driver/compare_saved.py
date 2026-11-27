"""Source-bound, saved-only controlled comparison; legal judgments stay unresolved."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path

FACTORS = {
    'visibility_clear_vs_occluded': ('measure_visibility',),
    'oncoming_far_vs_near': ('measure_oncoming',),
    'approaching_response': ('measure_opposite_response',),
    'overtaken_response': ('measure_overtaken_response',),
    'passing_completion': ('measure_completion','measure_left_pass'),
}

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def read(path):
    return json.loads(Path(path).read_text())

def source_report(folder, case_id, diagnostic):
    folder=Path(folder).resolve()
    provenance=read(folder/'acquisition-provenance.json')
    if diagnostic:
        if provenance.get('diagnostic_fixture') is not True:
            raise ValueError('positive CPU comparison requires explicit diagnostic fixture')
    elif provenance.get('diagnostic_fixture') is True:
        raise ValueError('synthetic fixture cannot establish Native comparison')
    report=read(folder/'analysis-report.json')
    if report.get('case_id')!=case_id or report.get('analysis_complete') is not True:
        raise ValueError('saved analysis case identity or completeness differs')
    for key, measurement in report.get('measurements',{}).items():
        sources=measurement.get('sources')
        if not sources:
            raise ValueError('measurement lacks original source binding: '+key)
        for name, expected in sources.items():
            if sha(folder/name)!=expected:
                raise ValueError('saved original source changed: '+name)
    if not diagnostic:
        pixel=read(folder/'pixel-review.json')
        if pixel.get('case_id')!=case_id or pixel.get('actual_pixels_visible') is not True:
            raise ValueError('independent actual pixel review missing')
        result=read(folder/'result.json')
        if result.get('physical_checks',{}).get('attempt',{}).get('status')!='met':
            raise ValueError('Native physical completion unconfirmed')
    return report

def audit(plan_path,left_path,right_path,comparison_id,diagnostic=False):
    plan=read(plan_path)
    comparison=next((row for row in plan['comparisons'] if row['comparison_id']==comparison_id),None)
    if comparison is None or comparison_id not in FACTORS:
        raise ValueError('unknown exact comparison')
    cases=comparison['case_ids']
    left=source_report(left_path,cases[0],diagnostic)
    right=source_report(right_path,cases[1],diagnostic)
    left_road=read(Path(left_path)/'road-context.json')
    right_road=read(Path(right_path)/'road-context.json')
    if left_road!=right_road:
        raise ValueError('reviewed highway fixed condition differs')
    for name in ('map.source','centerline.source'):
        if sha(Path(left_path)/'reviewed-sources'/name)!=sha(Path(right_path)/'reviewed-sources'/name):
            raise ValueError('reviewed road source differs: '+name)
    for a,b in ((left_path,right_path),):
        lc,rc=read(Path(a)/'config.json'),read(Path(b)/'config.json')
        for key in ('law_id','cell_id','actor','rate_hz','duration_s','cameras','physical_completion'):
            if lc.get(key)!=rc.get(key):
                raise ValueError('shared construction contract differs: '+key)
    factors=FACTORS[comparison_id]
    a,b=left['measurements'],right['measurements']
    if set(a)!=set(b) or not set(factors)<=set(a):
        raise ValueError('measurement inventory differs')
    for key in sorted(set(a)-set(factors)):
        if a[key]['value']!=b[key]['value']:
            raise ValueError('uncontrolled measured condition differs: '+key)
    if any(a[factor]['value']==b[factor]['value'] for factor in factors):
        raise ValueError('declared factor has no measured difference')
    if comparison_id=='approaching_response':
        if a['measure_oncoming']['value']['forward_station_gap_m']!=b['measure_oncoming']['value']['forward_station_gap_m']:
            raise ValueError('opposite initial station was not held fixed')
    return {'format':'worker-source-bound-comparison-audit-diagnostic' if diagnostic else 'worker-source-bound-comparison-audit',
            'comparison_id':comparison_id,'case_ids':cases,'factor_measurements':list(factors),
            'fixed_measurements':sorted(set(a)-set(factors)),
            'left_report_sha256':sha(Path(left_path)/'analysis-report.json'),
            'right_report_sha256':sha(Path(right_path)/'analysis-report.json'),
            'legal_judgment':'unresolved','physical_acceptance_claimed':False}

def main():
    p=argparse.ArgumentParser();p.add_argument('--plan',type=Path,required=True)
    p.add_argument('--left-attempt',type=Path,required=True);p.add_argument('--right-attempt',type=Path,required=True)
    p.add_argument('--comparison',required=True);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--diagnostic-protocol',action='store_true');args=p.parse_args()
    result=audit(args.plan,args.left_attempt,args.right_attempt,args.comparison,args.diagnostic_protocol)
    if args.output.exists():raise ValueError('retain prior comparison audit output')
    args.output.write_text(json.dumps(result,indent=2)+'\n');print(result['comparison_id'])
if __name__=='__main__':main()
