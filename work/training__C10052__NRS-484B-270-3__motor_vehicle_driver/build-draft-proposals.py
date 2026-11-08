"""Build source-bound, unselected C10052 stop and park package request rows."""
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent


def build():
    plan=json.loads((HERE/'case-plan.json').read_text())
    manifest=json.loads((HERE/'draft-execution-manifest.json').read_text())
    if manifest['status']!='draft_not_selected':raise ValueError('Unexpected delivery selection')
    park=json.loads((HERE/'draft-park-execution-manifest.json').read_text())
    entries=manifest['cases']+park['cases']
    drafts={row['case_id']:row for row in plan['cases']}
    cases=[]
    for entry in entries:
        draft=drafts[entry['case_id']]
        construction=json.loads((HERE/entry['construction']).read_text())
        config=json.loads(next(f['content'] for f in construction['files'] if f['path']=='config.json'))
        suffix=draft['case_id'].rsplit('__',1)[-1]
        requested={'stationary_facility_overlap_target_m2':
            0.0 if suffix=='probe_a' else 9.36}
        if suffix.startswith('probe_park_'):
            requested['sustained_applied_hand_brake']=suffix=='probe_park_held'
        cases.append({'case_id':draft['case_id'],'target_law_id':draft['target_law_id'],
            'target_type':'attempt','cell_id':plan['cell_id'],'actor':plan['actor'],
            'recording_description':config['recording_description'],'sweep_measurements':[],
            'comparison_variable':draft['comparison_variable'],
            'requested_setting':requested,
            'status':'draft_not_selected'})
    output=HERE/'proposals/cases.json';output.parent.mkdir(exist_ok=True)
    output.write_text(json.dumps({'cases':cases},indent=2)+'\n')
    return {'cases':len(cases),'selected':False}


if __name__=='__main__':print(json.dumps(build(),indent=2))
