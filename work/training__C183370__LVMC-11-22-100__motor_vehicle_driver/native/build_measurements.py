"""Generate exact C183370 source-bound diagnostic measurement contracts."""
import json
from pathlib import Path

from recording_contract import ASSIGNMENT

PACKAGE=Path(__file__).resolve().parents[1]


def contract(case, plan):
    case_id=ASSIGNMENT+'__'+case
    dispositions=plan['requirement_dispositions']
    mapping={'text-0':('surveyed_pavement_contact',
                       'measure_surveyed_pavement_contact'),
             'reviewed-scope-0':('warning_person_vicinity',
                                 'measure_warning_person_vicinity')}
    rows=[]
    for index,item in enumerate(dispositions):
        if (item['status']!='selected_required' or
                case_id not in item.get('case_ids',[])):
            continue
        key,method=mapping[item['requirement']]
        rows.append({'disposition_index':index,
                     'requirement':item['requirement'],
                     'source':item['source'],
                     'output_key':key,'method':method,
                     'value_type':'object','kind':'measured',
                     'inputs':['native-actors.jsonl','video_frames.jsonl',
                               'live-readback.json']})
    if len(rows)!=2:
        raise ValueError('Exact warned-pavement requirements changed')
    return {'format':'worker-measurement-contract',
            'case_id':case_id,'requirements':rows,
            'negative':{'remove':['live-readback.json'],
                        'error_contains':'Missing required source: live-readback.json'},
            'scope':'Source-derived surveyed contact and person vicinity only; '
                    'actual warning, newly repaired status, employee exception '
                    'and legal verdict require independent original review.'}


def write():
    plan=json.loads((PACKAGE/'case-plan.json').read_text())
    target=PACKAGE/'selected-measurement-contracts'
    target.mkdir(exist_ok=True)
    for case in ('reference','contrast'):
        path=target/(case+'.json')
        path.write_text(json.dumps(contract(case,plan),indent=2,sort_keys=True)+'\n')


if __name__=='__main__':
    write()
