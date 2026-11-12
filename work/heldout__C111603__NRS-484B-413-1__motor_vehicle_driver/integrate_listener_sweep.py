"""Adopt three source-proven listener points into the selected delivery package."""
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import shutil

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
DRAFT=HERE/'listener-sweep'
ASSIGNMENT=HERE.name


def sha(path): return sha256(path.read_bytes()).hexdigest()


def read(path): return json.loads(path.read_text())


def save(path,value): path.write_text(json.dumps(value,indent=2)+'\n')


plan=read(HERE/'case-plan.json')
proposal=read(HERE/'proposals/cases.json')
draft_plan=read(DRAFT/'case-plan.json')
draft_proposals=read(DRAFT/'proposals/cases.json')
for offset,draft_case,draft_proposal in zip((2,4,6),draft_plan['cases'],draft_proposals['cases']):
    prefix=f'listener-{offset}m'
    case=ASSIGNMENT+f'__ped_horn_listener_{offset}m'
    if not any(row['case_id']==case for row in plan['cases']):
        row=deepcopy(draft_case)
        row['construction_status']='selected_required_exact_primary_and_three_fallbacks_cpu_proven'
        plan['cases'].append(row)
    if not any(row['case_id']==case for row in proposal['cases']):
        row=deepcopy(draft_proposal)
        row['variable_assignments']['listener_route_lateral_offset_m']={
            'kind':'world_setup','value':offset}
        proposal['cases'].append(row)
    for disposition in plan['requirement_dispositions']:
        if 'ped_horn_audio' in ' '.join(disposition.get('case_ids',[])) and case not in disposition['case_ids']:
            disposition['case_ids'].append(case)
    for observation in plan['observations']:
        if observation['name']=='turn_signal_observation' and case not in observation['case_ids']:
            observation['case_ids'].append(case)
    manifest_path=HERE/f'{prefix}-manifest.json'
    manifest=read(manifest_path)
    entry=manifest['cases'][0]
    receipt_source=ROOT/f'.runtime-work/c111603-{prefix}-delivery-attempt/compatibility.json'
    receipt=HERE/f'{prefix}-compatibility-receipt.json'
    shutil.copy2(receipt_source,receipt)
    analysis=HERE/f'{prefix}-analysis.log'
    negative=HERE/f'{prefix}-negative.log'
    shutil.copy2(ROOT/f'.runtime-work/c111603-{prefix}-delivery-attempt/compatibility-analysis.log',analysis)
    shutil.copy2(ROOT/f'.runtime-work/c111603-{prefix}-delivery-attempt/negative-analysis.log',negative)
    entry['offline']={'command':f'.venv-cpu/bin/python runtime.py offline --manifest work/{ASSIGNMENT}/{prefix}-manifest.json --case {case} --output .runtime-work/c111603-{prefix}-offline-b --python $PWD/.venv-cpu/bin/python',
        'exit_code':0,'log':f'{prefix}-offline.log','log_sha256':sha(HERE/f'{prefix}-offline.log'),
        'construction_sha256':entry['construction_sha256']}
    entry['compatibility']={'receipt':receipt.name,'sha256':sha(receipt),'log':analysis.name}
    entry['negative']={'log':negative.name}
    for candidate in entry['candidates']:
        name=candidate['id']
        stem=f'{prefix}-{name}'
        candidate['offline']={'command':f'.venv-cpu/bin/python runtime.py offline --manifest work/{ASSIGNMENT}/{prefix}-manifest.json --case {case} --candidate {name} --output .runtime-work/c111603-{stem}-offline --python $PWD/.venv-cpu/bin/python',
            'exit_code':0,'log':f'{stem}-offline.log',
            'log_sha256':sha(HERE/f'{stem}-offline.log'),
            'construction_sha256':candidate['construction_sha256']}
        candidate['compatibility']={'receipt':f'{stem}-receipt.json',
            'sha256':sha(HERE/f'{stem}-receipt.json'),
            'log':f'{stem}-analysis.log','negative_log':f'{stem}-negative.log'}
    saved=HERE/f'{prefix}-saved-receipt.json'
    entry['saved_processing']={'command':f'.venv-cpu/bin/python work/{ASSIGNMENT}/prove_listener_sweep_saved_staged.py',
        'exit_code':0,'log':'listener-sweep-saved-proof.log',
        'log_sha256':sha(HERE/'listener-sweep-saved-proof.log'),
        'receipt':saved.name,'receipt_sha256':sha(saved)}
    command=(f'.venv-cpu/bin/python work/{ASSIGNMENT}/listener_delivery_audit.py '
             f'--case {case} --attempt .runtime-work/c111603-{prefix}-delivery-attempt '
             f'--output work/{ASSIGNMENT}/{prefix}-delivery-audit.json')
    entry['delivery_acceptance']={'case_id':case,'sets':['held-out'],
        'checks':['native_source','all_participants','time_join','full_video_decode',
                  'actual_pixels','physical_completion'],
        'script':'listener_delivery_audit.py','script_sha256':sha(HERE/'listener_delivery_audit.py'),
        'command':command,'test_exit_code':0,'test_log':f'{prefix}-delivery-audit.log',
        'test_log_sha256':sha(HERE/f'{prefix}-delivery-audit.log'),
        'negative_command':command+' --negative','negative_exit_code':1,
        'negative_expected_error':'Stale or missing original listener body source',
        'negative_log':f'{prefix}-delivery-negative.log',
        'negative_log_sha256':sha(HERE/f'{prefix}-delivery-negative.log')}
    entry['post_capture']={'recorded_only':True,
        'command':f'.venv-cpu/bin/python runtime.py process-saved --manifest work/{ASSIGNMENT}/execution-manifest.json --case {case} --attempt "$ATTEMPT" --output "$PROCESSING_OUTPUT" --library runtime/library --validator .runtime-work/fire-decoder/.lake/build/bin/adapterCheck',
        'feedback_command':'cat "$PROCESSING_OUTPUT/feedback.json"',
        'test_log':'listener-sweep-saved-proof.log',
        'test_log_sha256':sha(HERE/'listener-sweep-saved-proof.log'),'test_exit_code':0}
    save(manifest_path,manifest)
if not any(row['comparison_id']=='pedestrian_listener_distance' for row in plan['comparisons']):
    plan['comparisons'].append(draft_plan['comparisons'][0])
save(HERE/'case-plan.json',plan)
save(HERE/'proposals/cases.json',proposal)
print('Selected three listener points and bound exact draft receipts')
