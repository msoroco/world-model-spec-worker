"""Check that the authoritative plan retains every audited exception probe."""
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parent

def require(ok,message):
    if not ok:raise ValueError(message)

def audit():
    plan=json.loads((ROOT/'case-plan.json').read_text())
    matrix=json.loads((ROOT/'exception-case-matrix.json').read_text())
    cases={row['case_id']:row for row in plan['cases']}
    comparisons={row['comparison_id']:row for row in plan['comparisons']}
    require(len(cases)==len(plan['cases'])==30 and
            len(comparisons)==len(plan['comparisons'])==18,
            'Partial plan case/comparison count changed')
    for row in matrix['cases']:
        mapped=cases.get(row['case_id'])
        require(mapped and mapped['exception_spec']==row and
                mapped['planning_status']=='unverified_definition' and
                mapped['recorded_value'] is None,
                'Exact exception definition missing or altered: '+row['case_id'])
    for row in matrix['comparisons']:
        mapped=comparisons.get(row['comparison_id'])
        require(mapped and mapped['case_ids']==row['case_ids'] and
                mapped['deliberate_differences']==row['deliberate_differences'] and
                mapped['fixed_conditions']==row['fixed_conditions'] and
                mapped['status']=='planned_unverified',
                'Exact exception comparison missing or altered: '+row['comparison_id'])
    dispositions={row['requirement']:row for row in plan['requirement_dispositions']}
    for topic in ('text-3','text-4','text-5','text-6','text-7','text-8'):
        row=dispositions[topic]
        require(row['status']=='exception_pending' and row['case_ids'] and
                set(row['case_ids'])<=set(cases),
                'Exception disposition falsely selected or unassigned: '+topic)
    return {'format':'c150142-integrated-exception-plan-audit-v1',
            'passed':True,'planned_cases':30,'planned_comparisons':18,
            'exception_topics_pending':6,'original_native_observed':False}

if __name__=='__main__':print(json.dumps(audit(),sort_keys=True))
