"""Build unselected measurement contracts for all three exact source rows."""
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
PLAN=json.loads((HERE/'case-plan.json').read_text())
OUTPUTS=[('center_lane_activation_context','activation_context','sourced_context',['road_geometry.json']),
         ('after_left_turn_distance_interval','distance_after_turn','measured',['native_samples.jsonl','road_geometry.json']),
         ('turn_to_merge_scope','turn_merge_scope','measured',['native_samples.jsonl','road_geometry.json'])]


def build():
    out=HERE/'draft-measurements';out.mkdir(exist_ok=True)
    files=[]
    for case in PLAN['cases']:
        case_id=case['case_id'];suffix=case_id.rsplit('__',1)[-1]
        indices=[i for i,d in enumerate(PLAN['requirement_dispositions'])
                 if d['status']=='selected_required' and case_id in d['case_ids']]
        if len(indices)!=3:raise ValueError('Three exact source requirements expected')
        rows=[]
        for index,(key,method,kind,inputs) in zip(indices,OUTPUTS):
            source=PLAN['requirement_dispositions'][index]
            rows.append({'disposition_index':index,'requirement':source['requirement'],
                         'source':source['source'],'output_key':key,'method':method,
                         'value_type':'object','kind':kind,'inputs':inputs})
        contract={'format':'worker-measurement-contract-v1','case_id':case_id,
                  'requirements':rows,
                  'negative':{'remove':['native_samples.jsonl'],
                              'error_contains':'Missing required source: native_samples.jsonl'}}
        path=out/(suffix+'-contract.json')
        path.write_text(json.dumps(contract,indent=2)+'\n')
        files.append(str(path.relative_to(HERE)))
    return files


if __name__=='__main__':
    print(json.dumps({'draft_contracts':build(),'selected_delivery_cases':0},indent=2))
