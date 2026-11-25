"""Bind exact source-specific sidewalk compatibility inputs."""
import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
REPO=HERE.parents[1]
AID=HERE.name
sha=lambda path:hashlib.sha256(path.read_bytes()).hexdigest()


def write(path,obj):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(obj,indent=2,sort_keys=True)+'\n')


def main():
    selected=json.loads((HERE/'selected-offline-manifest.json').read_text())
    for entry in selected['cases']:
        suffix=entry['case_id'].rsplit('__',1)[-1]
        write(HERE/'cases'/suffix/'measurement-contract.json',{
            'format':'worker-measurement-contract','case_id':entry['case_id'],
            'requirements':[{'disposition_index':0,'requirement':'LVMC-11-40-140',
                'source':'inputs/planning/focused-coverage-20261016-v1/coverage-witnesses.json',
                'output_key':'measure','method':'measure','value_type':'object','kind':'measured',
                'inputs':['video_frames.jsonl','sidewalk-native.jsonl','sidewalk_context.json']}],
            'negative':{'remove':['sidewalk_context.json'],
                'error_contains':'Missing required source: sidewalk_context.json'}})
        entry.update(kind='delivery',measurement_contract=f'cases/{suffix}/measurement-contract.json',
            measurement_procedure={'entrypoint':'finalize_sidewalk.py',
                'output_schema':'worker-analysis-report-v1'},
            fixture_recipe=f'work/{AID}/cases/{suffix}/recipe.json',
            native_handoff={'python_env_var':'CARLA_PYTHON',
                'host_env_var':'CARLA_HOST','port_env_var':'CARLA_PORT'})
    write(HERE/'compat-draft-manifest.json',{'format':'worker-execution-manifest',
        'assignment_id':AID,'runtime_manifest_sha256':sha(REPO/'runtime/SOURCE-MANIFEST.json'),
        'status':'draft','delivery_ready':False,'cases':selected['cases']})
    print(json.dumps({'cases':[e['case_id'] for e in selected['cases']]},sort_keys=True))


if __name__=='__main__':
    main()
