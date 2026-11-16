"""Merge audited exception probes into the authoritative partial case plan."""
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

def integrate():
    path=ROOT/'case-plan.json'
    plan=json.loads(path.read_text())
    matrix=json.loads((ROOT/'exception-case-matrix.json').read_text())
    if plan['assignment_id']!=ROOT.name or matrix['assignment_id']!=ROOT.name:
        raise ValueError('Assignment identity changed')
    existing={row['case_id'] for row in plan['cases']}
    new_cases=[]
    for row in matrix['cases']:
        if row['case_id'] in existing:
            continue
        new_cases.append({'case_id':row['case_id'],
            'target_law_id':plan['law_id'],
            'planning_status':'unverified_definition',
            'target_type':'attempt',
            'comparison_variable':'red_curb_exception_context',
            'comparison_unit':'structured',
            'requested_setting':row['case_id'].rsplit('__',1)[-1],
            'recorded_value':None,
            'case_description':row['branch']+'; '+row['service_class']+
                '; requested stationary duration '+str(row['requested_stationary_duration_s'])+' s',
            'fixed_context':'Red-painted x=30..50 m curb and x=40 m parking target; '
                'compare only the variables named in the linked comparison; '
                'source-read back sign, vehicle, activity and mailbox facts.',
            'source_topic_ids':row['source_topic_ids'],
            'exception_spec':row})
    plan['cases'].extend(new_cases)
    comparison_ids={row['comparison_id'] for row in plan['comparisons']}
    for row in matrix['comparisons']:
        if row['comparison_id'] in comparison_ids:
            continue
        plan['comparisons'].append({'comparison_id':row['comparison_id'],
            'case_ids':row['case_ids'],
            'deliberate_differences':row['deliberate_differences'],
            'fixed_conditions':row['fixed_conditions'],
            'status':'planned_unverified'})
    all_cases={row['case_id'] for row in plan['cases']}
    if len(all_cases)!=len(plan['cases']) or len(plan['comparisons'])!=18:
        raise ValueError('Merged case/comparison count changed')
    for disposition in plan['requirement_dispositions']:
        topic=disposition['requirement']
        if topic=='text-3':
            matching={ROOT.name+'__reference',ROOT.name+'__ordinary_red_signed'}
        elif topic in ('text-4','text-5','text-6','text-7','text-8'):
            matching={row['case_id'] for row in matrix['cases']
                      if topic in row['source_topic_ids']}
        else:
            continue
        disposition['case_ids']=sorted(matching)
        disposition['evidence_or_gap']=(
            disposition['evidence_or_gap'].split('; no measured Native evidence')[0]
            + '; exact exception cases are planned but not Native-proven or selected.')
        if topic=='text-8':
            disposition['status']='exception_pending'
    path.write_text(json.dumps(plan,indent=2,allow_nan=False)+'\n')
    return {'cases':len(plan['cases']),'comparisons':len(plan['comparisons']),
            'new_cases':len(new_cases),'exception_dispositions_planned':6}

if __name__=='__main__':print(json.dumps(integrate(),sort_keys=True))
