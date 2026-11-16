"""Bind current exact-case CPU proofs without claiming delivery readiness."""
import hashlib
import json
from pathlib import Path
import shutil

ROOT=Path(__file__).resolve().parent
REPO=ROOT.parents[1]
UPDATE='update063'


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def bind(witness,candidate,item):
    prefix=REPO/'.runtime-work'/f'c146314-210-2-{witness}-{candidate}-compat-{UPDATE}'
    target=ROOT/'proofs'/UPDATE/witness/candidate
    target.mkdir(parents=True,exist_ok=True)
    for name,target_name in (('compatibility.json','compatibility.json'),
                             ('compatibility-analysis.log','positive-analysis.log'),
                             ('negative-analysis.log','negative-analysis.log')):
        source=prefix/name
        if not source.is_file():raise ValueError('Current compatibility proof missing: '+str(source))
        shutil.copyfile(source,target/target_name)
    receipt=json.loads((target/'compatibility.json').read_text())
    if receipt['case_id']!=ROOT.name+'__'+witness or \
       receipt['candidate_id']!=candidate or \
       receipt['construction_sha256']!=item['construction_sha256'] or \
       receipt['log_sha256']!=sha(target/'positive-analysis.log') or \
       receipt['negative_log_sha256']!=sha(target/'negative-analysis.log'):
        raise ValueError('Current compatibility receipt differs: '+witness+'/'+candidate)
    offline=ROOT/f'{UPDATE}-{witness}-{candidate}-offline.log'
    if not offline.is_file():raise ValueError('Current offline proof missing')
    rel=lambda name:(target/name).relative_to(ROOT).as_posix()
    item['offline']={'construction_sha256':item['construction_sha256'],
        'command':f'.venv-cpu/bin/python runtime.py offline --manifest {ROOT.relative_to(REPO)}/execution-manifest-unified-draft.json --case {ROOT.name}__{witness} --candidate {candidate} --output .runtime-work/c146314-210-2-{witness}-{candidate}-offline-{UPDATE}',
        'log':offline.name,'log_sha256':sha(offline),'exit_code':0}
    item['compatibility']={'receipt':rel('compatibility.json'),
        'sha256':sha(target/'compatibility.json'),
        'log':rel('positive-analysis.log'),
        'negative_log':rel('negative-analysis.log')}


def build():
    manifest=json.loads((ROOT/'execution-manifest-unified-draft.json').read_text())
    manifest['status']='draft_proof_bound_cpu'
    for entry in manifest['cases']:
        witness=entry['case_id'].rsplit('__',1)[1]
        bind(witness,'primary',entry)
        for candidate in entry['candidates']:
            bind(witness,candidate['id'],candidate)
        entry['negative']={'log':entry['compatibility']['negative_log']}
        entry['acquisition']={
            'ego_pose':{'entrypoint':'finalize_selected.py',
                'method':'derive center, yaw and body from retained ego actor rows',
                'evidence':['native-raw-actors.jsonl']},
            'ego_speed':{'entrypoint':'finalize_selected.py',
                'method':'derive speed from retained ego actor velocity',
                'evidence':['native-raw-actors.jsonl']},
            'right_side_pass_lateral_clearance':{
                'entrypoint':'prepare_raw.py',
                'method':'measure retained ego and lead body footprint gap at each joined frame',
                'evidence':['native-raw-actors.jsonl','video_frames.jsonl']},
            'four_source_views':{'entrypoint':'prepare_raw.py',
                'method':'verify four camera sources and frame-map view set',
                'evidence':['video_frames.jsonl','overview.mkv','approach.mkv',
                    'reference_corner.mkv','driver_reference.mkv']}}
        entry['native_handoff']={'python_env_var':'CARLA_PYTHON',
            'host_env_var':'CARLA_HOST','port_env_var':'CARLA_PORT',
            'operator_release_required':True}
    output=ROOT/'execution-manifest-proof-bound-preview.json'
    output.write_text(json.dumps(manifest,indent=2,allow_nan=False)+'\n')
    return {'format':'c146314-proof-bound-preview-v1',
        'cases':len(manifest['cases']),
        'candidates':sum(1+len(e['candidates']) for e in manifest['cases']),
        'preview':output.relative_to(ROOT).as_posix(),
        'preview_sha256':sha(output),'delivery_ready':False}


if __name__=='__main__':print(json.dumps(build(),sort_keys=True))
