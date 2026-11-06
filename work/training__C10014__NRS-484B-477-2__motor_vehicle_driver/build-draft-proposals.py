"""Build two source-bound, unselected C10014 package request rows."""
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent


def build():
    plan=json.loads((HERE/'case-plan.json').read_text())
    manifest=json.loads((HERE/'draft-execution-manifest.json').read_text())
    if manifest['status']!='draft_not_selected':raise ValueError('Unexpected delivery selection')
    cases=[]
    for draft,entry in zip(plan['cases'],manifest['cases']):
        if draft['case_id']!=entry['case_id']:raise ValueError('Case identity differs')
        construction=json.loads((HERE/entry['construction']).read_text())
        config=json.loads(next(f['content'] for f in construction['files'] if f['path']=='config.json'))
        cases.append({'case_id':draft['case_id'],'target_law_id':draft['target_law_id'],
            'target_type':draft['target_type'],'cell_id':plan['cell_id'],'actor':plan['actor'],
            'recording_description':config['recording_description'],'sweep_measurements':[],
            'comparison_variable':draft['comparison_variable'],
            'requested_setting':{'stationary_entrance_overlap_target_m':
                0.0 if draft['case_id'].endswith('__reference') else 5.2},
            'status':'draft_not_selected'})
    output=HERE/'proposals/cases.json';output.parent.mkdir(exist_ok=True)
    output.write_text(json.dumps({'cases':cases},indent=2)+'\n')
    return {'cases':len(cases),'selected':False}


if __name__=='__main__':print(json.dumps(build(),indent=2))
