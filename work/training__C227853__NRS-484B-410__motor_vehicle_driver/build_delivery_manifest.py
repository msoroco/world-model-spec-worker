"""Bind selected parked-departure CPU diagnostics to exact source contracts."""
import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
ASSIGNMENT=HERE.name


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,indent=2,allow_nan=False)+'\n')


def build():
    draft=json.loads((HERE/'draft-departure-manifest.json').read_text())
    selected=[]
    for item in draft['cases']:
        case=item['case_id']
        suffix=case.rsplit('__',1)[-1]
        construction=json.loads((HERE/item['construction']).read_text())
        config=json.loads(next(file['content'] for file in construction['files']
                               if file['path']=='config.json'))
        contract={'format':'worker-measurement-contract','case_id':case,
            'requirements':[{'disposition_index':0,'requirement':'NRS-484B-410',
                'source':'NRS 484B.410','output_key':'departure_observation',
                'method':'departure_observation','value_type':'object','kind':'measured',
                'inputs':['departure-trace.jsonl','video_frames.jsonl',
                          'departure-context.json','road.xodr']}],
            'negative':{'remove':['departure-context.json'],
                        'error_contains':'Missing required source: departure-context.json'}}
        write(HERE/('measurement-'+suffix+'.json'),contract)
        item.update(measurement_contract='measurement-'+suffix+'.json',
            measurement_procedure={'entrypoint':'finalize.py',
                                   'output_schema':'c227853-departure-analysis-v1'},
            fixture_recipe='work/'+ASSIGNMENT+'/selected-recipe-'+suffix+'.json')
        selected.append({'case_id':case,'target_law_id':'NRS-484B-410',
            'target_type':'judgment_sweep',
            'rationale':'Source-shaped parked-highway departure contrast',
            'paired_probe_id':ASSIGNMENT+'__comparison',
            'deliberate_differences':['initial approaching traffic position'],
            'probe':{'primary_variable':'initial_approaching_traffic_position',
                     'comparison_or_standard':'paired clearance and conflict contrast',
                     'target_value_or_branch':suffix},
            'variable_assignments':{'initial_approaching_traffic_position':{
                'kind':'controller','value':-55 if suffix=='controlled_2' else 15}},
            'recording_description':config['recording_description'],
            'unresolved_judgment_calls':['with safety','Nevada public highway',
                                         'parking permission and statutory exception']})
    write(HERE/'proposals/cases.json',{'cell_id':'C227853',
        'actor':'motor_vehicle_driver','status':'draft','cases':selected})
    draft['format']='worker-execution-manifest'
    write(HERE/'execution-manifest.json',draft)
    return {'selected_case_ids':[entry['case_id'] for entry in draft['cases']],
            'execution_manifest_sha256':sha(HERE/'execution-manifest.json')}


if __name__=='__main__':
    print(json.dumps(build()))
