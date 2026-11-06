"""Build two unselected semantic-stage proposals from exact case identities."""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def main():
    plan = json.loads((HERE/'case-plan.json').read_text())
    manifest = json.loads((HERE/'draft-execution-manifest.json').read_text())
    cases = []
    for case in plan['cases']:
        entry = next(item for item in manifest['cases'] if item['case_id'] == case['case_id'])
        construction = json.loads((HERE/entry['construction']).read_text())
        config = json.loads(next(item['content'] for item in construction['files']
                                 if item['path'] == 'config.json'))
        cases.append({'case_id':case['case_id'], 'target_law_id':'NRS-484B-127-1',
                      'target_type':'planned_delivery_comparison',
                      'cell_id':'C102304','actor':'motor_vehicle_driver',
                      'recording_description':config['recording_description'],
                      'sweep_measurements':[],
                      'comparison_variable':'realized_following_gap',
                      'requested_setting_m':10 if config['case_suffix']=='condition_a' else 25,
                      'status':'draft_not_selected',
                      'legal_judgment':'reasonable_and_prudent_unresolved'})
    output = HERE/'proposals/cases.json'
    output.parent.mkdir(exist_ok=True)
    output.write_text(json.dumps({'cases':cases},indent=2)+'\n')
    print(json.dumps({'unselected_proposals':len(cases),
                      'legal_outcomes_claimed':0},sort_keys=True))


if __name__ == '__main__':
    main()
