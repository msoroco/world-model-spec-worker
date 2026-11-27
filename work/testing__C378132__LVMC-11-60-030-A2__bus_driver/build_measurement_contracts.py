"""Bind every selected statutory requirement to source-bound saved measurements."""
from pathlib import Path
import json

ROOT=Path(__file__).resolve().parent
METHODS=('measure_bus_class','measure_street','measure_loading_purpose',
         'measure_bus_stop','measure_bus_stand','measure_loading_zone',
         'measure_route_endpoint','measure_footprint','measure_emergency')
KEYS=('bus_class','street','loading_purpose','bus_stop','bus_stand',
      'loading_zone','route_endpoint','footprint','emergency')
INPUTS=('location-source-packet.json','site.json','designation.json','route.json',
        'identity.json','activity.json','purpose.json','circumstances.json','native.json')

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
    print(f"{len(plan['cases'])} nine-requirement selected measurement contracts")

if __name__=='__main__':
    build()
