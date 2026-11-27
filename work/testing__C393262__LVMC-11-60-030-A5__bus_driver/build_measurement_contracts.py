"""Bind every selected statutory requirement to source-bound saved measurements."""
from pathlib import Path
import json

ROOT=Path(__file__).resolve().parent
METHODS=('measure_bus_identity','measure_stop_designation','measure_designated_limit',
         'measure_activity_interval','measure_duration_relation')
KEYS=('bus_identity','stop_designation','designated_limit','activity_interval','duration_relation')
INPUTS=('duration-source-packet.json','site.json','designation.json','identity.json','activity.json','native.json')

def build():
    plan=json.loads((ROOT/'case-plan.json').read_text())
    for case in plan['cases']:
        folder=ROOT/'cases'/case['case_id'].split('__')[-1]
        rows=[]
        for i,disposition in enumerate(plan['requirement_dispositions']):
            rows.append({'disposition_index':i,'requirement':disposition['requirement'],
                         'source':disposition['source'],'kind':'measured','method':METHODS[i],
                         'output_key':KEYS[i],'value_type':'object','inputs':list(INPUTS)})
        contract={'format':'worker-measurement-contract','requirements':rows,
                  'negative':{'remove':['designation.json'],
                              'error_contains':'Missing required source: designation.json'}}
        (folder/'measurement-contract.json').write_text(json.dumps(contract,indent=2,sort_keys=True)+'\n')
    print('six five-requirement selected measurement contracts')

if __name__=='__main__':
    build()
