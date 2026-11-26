"""Build exact selected CPU draft with seven case measurement contracts."""
import hashlib
import json
from pathlib import Path
from build_selected import build
from parking_scene import CASES

PKG=Path(__file__).resolve().parents[1]
A=PKG.name


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    batch=json.loads(Path('batch.json').read_text())
    plan=json.loads((PKG/'case-plan.json').read_text())
    dispositions=plan['requirement_dispositions']
    cases=[]
    for suffix in CASES:
        primary=build(suffix)
        cid=primary['case_id']
        construction=json.loads((PKG/primary['construction']).read_text())
        rows=[]
        output_keys={0:'default_position_measurement',1:'left_ordinance_measurement',
                     2:'angle_ordinance_measurement',3:'reviewed_scope_measurement'}
        for index,d in enumerate(dispositions):
            if d['status']=='selected_required' and cid in d.get('case_ids',[]):
                rows.append({'disposition_index':index,'requirement':d['requirement'],
                    'source':d['source'],'kind':'measured','method':'measure_reference',
                    'output_key':output_keys[index],'value_type':'object',
                    'inputs':['parking-context.json','native-parking.jsonl','video_frames.jsonl']})
        contract={'format':'worker-measurement-contract','case_id':cid,
            'status':'selected_cpu_draft',
            'negative':{'remove':['parking-context.json'],
                        'error_contains':'Missing required source: parking-context.json'},
            'requirements':rows,'source_cameras':['overview','approach','reference_corner','driver_reference'],
            'legal_compliance':'unassessed'}
        contract_path=PKG/'native'/f'{suffix}-measurement-contract.json'
        contract_path.write_text(json.dumps(contract,indent=2)+'\n')
        entry={'case_id':cid,'kind':'delivery','construction':primary['construction'],
            'construction_sha256':primary['construction_sha256'],
            'measurement_procedure':{'entrypoint':'finalize.py'},
            'measurement_contract':str(contract_path.relative_to(PKG)),
            'fixture_recipe':str(Path('work')/A/'native'/f'diagnostic-{suffix}-fixture-recipe.json'),
            'recording_description':construction['recording_description'],
            'native_handoff':{'python_env_var':'CARLA_PYTHON','host_env_var':'CARLA_HOST',
                              'port_env_var':'CARLA_PORT'},'candidates':[]}
        if suffix.startswith('angle'):
            fallback=build(suffix,'fallback1')
            entry['candidate_risk']={'status':'physical',
                'reason':'Angled vehicle spawn may intersect curb surface'}
            entry['candidates']=[{'id':'fallback1','construction':fallback['construction'],
                'construction_sha256':fallback['construction_sha256'],
                'trigger':{'source':'Native try_spawn_actor','metric':'actor spawn result',
                           'failure_condition':'spawn returns None'},
                'changed_knobs':['spawn height from 1.5m to 1.8m']}]
        cases.append(entry)
    manifest={'format':'worker-execution-manifest','assignment_id':A,'status':'draft',
        'runtime_manifest_sha256':batch['runtime']['source_manifest_sha256'],
        'physical_acceptance_claimed':False,'cases':cases}
    path=PKG/'draft-native-manifest.json';path.write_text(json.dumps(manifest,indent=2)+'\n')
    return {'cases':len(cases),'candidates':sum(1+len(x['candidates']) for x in cases),
            'manifest_sha256':sha(path)}


if __name__=='__main__':print(json.dumps(main(),indent=2))
