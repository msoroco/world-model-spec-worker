"""Bind four draft cases to current runtime and source-shaped diagnostic contracts."""
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
REPO=ROOT.parents[1]
RUNTIME=REPO/'runtime'


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,indent=2)+'\n')


def build():
    draft=json.loads((ROOT/'draft-native-manifest.json').read_text())
    entries=[]
    for item in draft['cases']:
        suffix=item['case_id'].rsplit('__',1)[1]
        pedestrian=suffix.startswith('pedestrian_')
        contract={'format':'worker-measurement-contract','case_id':item['case_id'],
            'requirements':[{'disposition_index':1 if pedestrian else 0,
                'requirement':'NRS-484B-113-3','source':'NRS 484B.113(3)',
                'output_key':'pedestrian_requirement' if pedestrian else 'moving_requirement',
                'method':'measure_pedestrian_requirement' if pedestrian else 'measure_moving_requirement',
                'value_type':'object','kind':'measured',
                'inputs':['native-motion.jsonl','traffic-context.json','video_frames.jsonl']}],
            'negative':{'remove':['traffic-context.json'],
                'error_contains':'Missing required source: traffic-context.json'}}
        contract_path=ROOT/'native/bundles'/suffix/'measurement-contract.json'
        write(contract_path,contract)
        entry=dict(item)
        entry.pop('delivery_readiness',None)
        entry.update(measurement_contract=str(contract_path.relative_to(ROOT)),
            measurement_procedure={'entrypoint':'finalize.py',
                'output_schema':'c230259-saved-measurement-v1'},
            fixture_recipe=str((ROOT/('diagnostic-'+suffix+'-recipe.json')).relative_to(REPO)),
            native_handoff={'python_env_var':'CARLA_PYTHON','host_env_var':'CARLA_HOST',
                'port_env_var':'CARLA_PORT'})
        entries.append(entry)
    manifest={'format':'worker-execution-manifest','assignment_id':ROOT.name,
        'runtime_manifest_sha256':sha(RUNTIME/'SOURCE-MANIFEST.json'),
        'status':'partial','cases':entries}
    write(ROOT/'execution-manifest.json',manifest)
    primary=json.loads((ROOT/entries[0]['construction']).read_text())
    write(ROOT/'construction.json',primary)
    for file in primary['files']:
        target=ROOT/file['path'];target.parent.mkdir(parents=True,exist_ok=True)
        target.write_text(file['content'])
    print(json.dumps({'cases':len(entries),'runtime_manifest_sha256':manifest['runtime_manifest_sha256']}))


if __name__=='__main__':build()
