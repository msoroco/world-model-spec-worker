"""Build five unselected, exact-clause measurement contract drafts."""
import json
from pathlib import Path

FOLDER=Path(__file__).resolve().parent
PLAN=json.loads((FOLDER/'case-plan.json').read_text())


def build():
    output=FOLDER/'draft-measurements';output.mkdir(exist_ok=True)
    records=[]
    for case in PLAN['cases']:
        case_id=case['case_id'];suffix=case_id.split('__')[-1]
        indices=[i for i,row in enumerate(PLAN['requirement_dispositions'])
                 if row['status']=='selected_required' and case_id in row['case_ids']]
        if len(indices)!=1:raise ValueError('Draft case needs exactly one selected-required source disposition: '+case_id)
        index=indices[0];disposition=PLAN['requirement_dispositions'][index]
        contract={'format':'worker-measurement-contract-v1','case_id':case_id,
          'requirements':[{'disposition_index':index,
            'requirement':disposition['requirement'],'source':disposition['source'],
            'output_key':'center_lane_entry_to_turn_distance','method':'measure_entry_to_turn',
            'value_type':'object','kind':'measured',
            'inputs':['native_samples.jsonl','road_geometry.json']}],
          'negative':{'remove':['native_samples.jsonl'],
                      'error_contains':'Missing required source: native_samples.jsonl'}}
        path=output/(suffix+'-contract.json');path.write_text(json.dumps(contract,indent=2)+'\n')
        records.append(str(path.relative_to(FOLDER)))
    return records


if __name__=='__main__':print(json.dumps({'draft_contracts':build(),'selected_delivery_cases':0},indent=2))
