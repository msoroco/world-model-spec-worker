"""Controlled original-source comparison of exact LVMC service parking cases."""
import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CONDITIONS = ('work_kind','work_near','length_ft','unladen_lb','adjacent_kind',
              'frontage_ft','posted_permission','loading')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def audit(comparison_id, report_dir, *, synthetic_fixture=False):
    plan=json.loads((ROOT/'case-plan.json').read_text())
    comparison=next((x for x in plan['comparisons'] if x['comparison_id']==comparison_id),None)
    if comparison is None or len(comparison['case_ids'])!=2:
        raise ValueError('unknown exact service parking comparison')
    report_dir=Path(report_dir)
    reports=[]
    for case_id in comparison['case_ids']:
        path=report_dir/(case_id.rsplit('__',1)[-1]+'.json')
        report=json.loads(path.read_text())
        expected='synthetic CPU audit proof only' if synthetic_fixture else 'original Native delivery review'
        if (report.get('format')!='worker-delivery-audit' or report.get('passed') is not True or
                report.get('case_id')!=case_id or report.get('scope')!=expected or
                report.get('physical_completion_reviewed') is not True or
                report.get('legal_verdict_claimed') is not False):
            raise ValueError('source-bound exact delivery audit missing: '+case_id)
        reports.append((path,report))
    fixed=('cell_id','actor','camera_contract_sha256','duration_s','candidate_id',
           'street_public','city_jurisdiction','governed_curb_rect_m')
    first,second=(report for _,report in reports)
    if any(first.get(name)!=second.get(name) for name in fixed):
        raise ValueError('controlled service parking comparison changed fixed conditions')
    different={name for name in CONDITIONS if first['case_conditions'].get(name)!=second['case_conditions'].get(name)}
    declared=set(comparison['deliberate_differences'])
    if different != declared:
        raise ValueError('measured case differences do not match declared comparison: '+str(sorted(different)))
    if first['measured']['parked_frames']!=second['measured']['parked_frames']:
        raise ValueError('parked interval changed across controlled comparison')
    return {'format':'worker-comparison-audit','passed':True,
            'comparison_id':comparison_id,'case_ids':comparison['case_ids'],
            'reports_sha256':{path.name:sha(path) for path,_ in reports},
            'fixed_conditions_checked':list(fixed),
            'deliberate_differences':comparison['deliberate_differences'],
            'varied_conditions':sorted(different),
            'scope':'synthetic CPU comparison proof only' if synthetic_fixture else 'original Native delivery review',
            'legal_verdict_claimed':False}

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--comparison',required=True)
    parser.add_argument('--report-dir',required=True)
    args=parser.parse_args()
    print(json.dumps(audit(args.comparison,args.report_dir),indent=2))
