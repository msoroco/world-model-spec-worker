"""Validate a source-bound local comparison review after Native capture.

The operator supplies a report with exact case paths, measured fixed conditions,
and measured deliberate differences. This check does not infer legal conclusions.
"""
import argparse
import hashlib
import json
from pathlib import Path

def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def check(repo, assignment, comparison_id, report_path):
    repo=Path(repo).resolve()
    plan=json.loads((repo/'work'/assignment/'case-plan.json').read_text())
    comparison=next(c for c in plan['comparisons'] if c['comparison_id']==comparison_id)
    report=json.loads(Path(report_path).read_text())
    cases=set(comparison['case_ids'])
    if (report.get('format')!='worker-native-comparison-review' or
            report.get('assignment_id')!=assignment or
            report.get('comparison_id')!=comparison_id or
            set(report.get('cases',{}))!=cases or
            not report.get('reviewer') or report.get('diagnostic_fixture') is not False):
        raise ValueError('Comparison review identity, scope or case set mismatch')
    for cid,item in report['cases'].items():
        attempt=Path(item['attempt']).resolve()
        sources=item.get('source_sha256',{})
        if not sources or not item.get('original_source_paths') or not set(item['original_source_paths']) <= set(sources):
            raise ValueError('Missing original source hashes: '+cid)
        for name,expected in sources.items():
            path=(attempt/name).resolve()
            if attempt not in path.parents or digest(path)!=expected:
                raise ValueError('Changed original source: '+cid+'/'+name)
        if item.get('audit_case_id')!=cid or item.get('audit_passed') is not True:
            raise ValueError('Missing accepted exact-case source audit: '+cid)
    for field,conditions,different in (
            ('fixed_measurements',comparison['fixed_conditions'],False),
            ('difference_measurements',comparison['deliberate_differences'],True)):
        measured=report.get(field,{})
        if set(measured)!=set(conditions):
            raise ValueError('Unreviewed comparison condition: '+comparison_id)
        for condition,by_case in measured.items():
            if set(by_case)!=cases or any(value is None for value in by_case.values()):
                raise ValueError('Incomplete comparison measurement: '+condition)
            values={json.dumps(value,sort_keys=True) for value in by_case.values()}
            if (len(values)>1)!=different:
                raise ValueError('Fixed/different condition failed: '+condition)
    if report.get('passed') is not True:
        raise ValueError('Comparison review did not pass')
    return {'assignment_id':assignment,'comparison_id':comparison_id,
            'case_count':len(cases),'source_bound':True,'passed':True}

if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--repo',required=True)
    p.add_argument('--assignment',required=True)
    p.add_argument('--comparison',required=True)
    p.add_argument('--report',required=True)
    a=p.parse_args()
    print(json.dumps(check(a.repo,a.assignment,a.comparison,a.report),indent=2))
