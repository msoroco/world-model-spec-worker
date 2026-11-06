"""Build source-bound, unselected proposal rows for diagnostic compatibility."""
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
TARGET_FEET={'witness_1':180,'witness_2':220,
             'numeric_1_0':199,'numeric_1_1':200,'numeric_1_2':201}


def build():
    plan=json.loads((HERE/'case-plan.json').read_text())
    manifest=json.loads((HERE/'draft-execution-manifest.json').read_text())
    if manifest['status']!='draft_not_selected':
        raise ValueError('Unexpected delivery selection')
    cases=[]
    for draft,entry in zip(plan['cases'],manifest['cases']):
        if draft['case_id']!=entry['case_id']:
            raise ValueError('Case ordering or identity differs')
        suffix=draft['case_id'].rsplit('__',1)[-1]
        construction=json.loads((HERE/entry['construction']).read_text())
        config=json.loads(next(f['content'] for f in construction['files'] if f['path']=='config.json'))
        cases.append({'case_id':draft['case_id'],'target_law_id':draft['target_law_id'],
                      'target_type':draft['target_type'],'cell_id':plan['cell_id'],
                      'actor':plan['actor'],'recording_description':config['recording_description'],
                      'sweep_measurements':[],
                      'comparison_variable':draft['comparison_variable'],
                      'requested_setting':{'center_turn_lane_entry_to_left_turn_ft':TARGET_FEET[suffix]},
                      'status':'draft_not_selected'})
    path=HERE/'proposals/cases.json';path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps({'cases':cases},indent=2)+'\n')
    return path


if __name__=='__main__':print(build())
