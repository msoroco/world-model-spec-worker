"""Deterministically extend the C125714 inline package with the controller pair."""
import copy
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parent
BASE='testing__C125714__NRS-484B-250-2__motor_vehicle_driver'
LABELS=('yield_wait_for_other_clear','advance_at_release')
POLICY=dict(zip(LABELS,('wait_for_other_clear','advance_at_release')))
COMMON=('runner.py','native_crossing.py','entry_timing.py','saved_finalizer.py',
        'analysis.py','native_capture.py','native_body_capture.py',
        'branch_alternatives.py','controlled_yielding.py')
TESTS=('tests/test_native_capture.py','tests/test_branch_alternatives.py',
       'tests/test_controlled_yielding.py')


def write(path,value):
    path.write_text(json.dumps(value,indent=2,allow_nan=False)+'\n')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    manifest_path=ROOT/'execution-manifest.json'
    manifest=json.loads(manifest_path.read_text())
    template=next(c for c in manifest['cases'] if c['case_id'].endswith('__timing_inside_training'))
    config=json.loads((ROOT/'config.json').read_text())
    ids=[BASE+'__'+label for label in LABELS]
    config['supported_case_ids']=list(dict.fromkeys(config['supported_case_ids']+ids))
    write(ROOT/'config.json',config)
    for c in manifest['cases']:
        folder=ROOT/c['construction']
        data=json.loads(folder.read_text())
        files={f['path']:f for f in data['files']}
        for name in COMMON+TESTS:
            if name in files:files[name]['content']=(ROOT/name).read_text()
            else:data['files'].append({'path':name,'source':str((ROOT/name).relative_to(Path.cwd())),
                                       'content':(ROOT/name).read_text()})
        files['config.json']['content']=json.dumps(dict(json.loads(files['config.json']['content']),
              supported_case_ids=config['supported_case_ids']),indent=2)+'\n'
        write(folder,data)
        c['construction_sha256']=sha(folder)
        c['offline']['construction_sha256']=c['construction_sha256']
    for label in LABELS:
        case=BASE+'__'+label
        if any(item['case_id']==case for item in manifest['cases']):
            continue
        folder=ROOT/'cases'/label
        entry=copy.deepcopy(template)
        entry['case_id']=case
        entry['construction']=str((folder/'construction.json').relative_to(ROOT))
        entry['measurement_contract']=str((folder/'measurement-contract.json').relative_to(ROOT))
        entry['fixture_recipe']=str((folder/'diagnostic-recipe.json').relative_to(Path.cwd()))
        entry['proof_status']='constructed_exact_controller_case_offline_compatibility_pending'
        entry['acquisition']['ego_original_brake']={'entrypoint':'native_capture.py',
            'evidence':'controller-history.jsonl','method':'original Native control each tick'}
        entry['offline']={};entry['compatibility']={};entry['negative']={}
        base_contract=json.loads((ROOT/template['measurement_contract']).read_text())
        base_contract['case_id']=case
        base_contract['requirements'][0]['inputs'].append('controller-history.jsonl')
        base_contract['requirements'][0]['method']='measure_original_entry_and_control'
        base_contract['unresolved_judgments'].append('whether original control and motion constitute right-of-way yielding')
        write(folder/'measurement-contract.json',base_contract)
        base_construction=json.loads((ROOT/template['construction']).read_text())
        base_construction['case_id']=case
        files={f['path']:f for f in base_construction['files']}
        scene=json.loads(files['scene.json']['content'])
        scene['case_id']=case;scene['control_policy']=POLICY[label]
        scene['requested_entry_offset_s']=-0.02500000037252903
        files['scene.json']['content']=json.dumps(scene,indent=2)+'\n'
        cfg=json.loads(files['config.json']['content'])
        cfg['selected_case_id']=case;cfg['supported_case_ids']=config['supported_case_ids']
        cfg['case']['case_id']=case
        cfg['case']['requested_entry_offset_s']=scene['requested_entry_offset_s']
        cfg['case']['recording_description']['limitations'].append(
            'Ego controller policy is an engineering intervention; original brake and entry timing are measured separately.')
        files['config.json']['content']=json.dumps(cfg,indent=2)+'\n'
        base_construction['recording_description']=cfg['case']['recording_description']
        for name in COMMON+TESTS:
            if name in files:files[name]['content']=(ROOT/name).read_text()
            else:base_construction['files'].append({'path':name,'source':str((ROOT/name).relative_to(Path.cwd())),
                                                    'content':(ROOT/name).read_text()})
        write(folder/'construction.json',base_construction)
        entry['construction_sha256']=sha(folder/'construction.json')
        manifest['cases'].append(entry)
    write(manifest_path,manifest)


if __name__=='__main__':
    main()
