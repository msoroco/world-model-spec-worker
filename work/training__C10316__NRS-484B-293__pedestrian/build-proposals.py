"""Build two unselected C10316 semantic stage proposals from exact cases."""
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent


def main():
    plan=json.loads((HERE/'case-plan.json').read_text())
    manifest=json.loads((HERE/'draft-execution-manifest.json').read_text())
    cases=[]
    for case in plan['cases']:
        entry=next(x for x in manifest['cases'] if x['case_id']==case['case_id'])
        construction=json.loads((HERE/entry['construction']).read_text())
        config=json.loads(next(x['content'] for x in construction['files'] if x['path']=='config.json'))
        suffix=config['case_suffix']
        cases.append({'case_id':case['case_id'],'target_law_id':'NRS-484B-293',
                      'target_type':'planned_delivery_comparison','cell_id':'C10316',
                      'actor':'pedestrian','recording_description':config['recording_description'],
                      'sweep_measurements':[],
                      'comparison_variable':'pedestrian_lateral_crosswalk_half',
                      'requested_setting':'right' if suffix=='reference' else 'left',
                      'requested_lateral_offset_m':-.65 if suffix=='reference' else .65,
                      'status':'draft_not_selected',
                      'practicability_judgment':'unresolved',
                      'legal_verdict_claimed':False})
    output=HERE/'proposals/cases.json';output.parent.mkdir(exist_ok=True)
    output.write_text(json.dumps({'cases':cases},indent=2)+'\n')
    print(json.dumps({'unselected_proposals':len(cases),'legal_outcomes_claimed':0},sort_keys=True))


if __name__=='__main__':main()
