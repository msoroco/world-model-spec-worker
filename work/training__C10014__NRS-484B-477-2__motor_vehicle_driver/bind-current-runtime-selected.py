"""Bind preserved exact alley cases to regenerated current-runtime CPU proofs."""
import hashlib
import json
import shutil
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
PREFIX = f'work/{HERE.name}/'
MANIFEST = HERE/'execution-manifest.json'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def require(ok, message):
    if not ok:
        raise ValueError(message)


def main():
    current = sha(ROOT/'runtime/pipeline/SOURCE-MANIFEST.json')
    harness = read(HERE/'current-runtime-reproof-manifest.json')
    progress = read(HERE/'current-runtime-matrix-progress.json')
    offline = read(HERE/'current-runtime-offline-reproof.json')
    require(harness['runtime_manifest_sha256'] == current and
            progress['runtime_manifest_sha256'] == current and progress['completed'] == 8 and
            len(progress['rows']) == len(offline['rows']) == 8,
            'Eight exact current-runtime chains are required')
    historical = HERE/'historical-execution-manifest-pre-cutover.json'
    if not historical.is_file():
        shutil.copyfile(MANIFEST,historical)
    old = read(historical)
    require(old['runtime_manifest_sha256'] != current, 'Historical manifest already current')
    expected = {e['case_id']: e for e in harness['cases']}
    require(set(expected) == {e['case_id'] for e in old['cases']}, 'Selected case set differs')
    for entry in old['cases']:
        selected = expected[entry['case_id']]
        suffix = entry['case_id'].rsplit('__',1)[-1]
        require(entry['construction_sha256'] == selected['construction_sha256'] and
                {c['id']:c['construction_sha256'] for c in entry['candidates']} ==
                {c['id']:c['construction_sha256'] for c in selected['candidates']},
                'Selected construction changed: '+suffix)
        for candidate in ('primary','fallback1','fallback2','fallback3'):
            chosen = entry if candidate == 'primary' else next(c for c in entry['candidates'] if c['id']==candidate)
            proof = HERE/'current-runtime-selected-proof'/suffix/candidate
            receipt = read(proof/'compatibility.json')
            saved = read(proof/'saved-processing.json')
            offlog = HERE/f'current-runtime-{suffix}-{candidate}-offline.log'
            require(receipt['passed'] and receipt['runtime_manifest_sha256'] == current and
                    receipt['construction_sha256'] == chosen['construction_sha256'] and
                    receipt['log_sha256'] == sha(proof/'analysis.log') and
                    receipt['negative_log_sha256'] == sha(proof/'negative-analysis.log') and
                    saved['passed'] and saved['recorded_only'] and not saved['missing_evidence'] and
                    saved['native_revision']['construction_sha256'] == chosen['construction_sha256'] and
                    read(offlog)['offline_passed'], 'Proof binding differs: '+suffix+' '+candidate)
            relative = f'current-runtime-selected-proof/{suffix}/{candidate}'
            chosen['offline'] = {'exit_code':0,'construction_sha256':chosen['construction_sha256'],
                'command':f'.venv-cpu/bin/python runtime.py offline --manifest {PREFIX}current-runtime-reproof-manifest.json '
                          f'--case {entry["case_id"]} --candidate {candidate} --output .runtime-work/c10014-current-offline',
                'log':offlog.name,'log_sha256':sha(offlog)}
            chosen['compatibility'] = {'receipt':relative+'/compatibility.json',
                'sha256':sha(proof/'compatibility.json'), 'log':relative+'/analysis.log',
                'negative_log':relative+'/negative-analysis.log'}
            chosen['saved_processing'] = {'receipt':relative+'/saved-processing.json',
                'sha256':sha(proof/'saved-processing.json')}
        entry['negative'] = {'log':f'current-runtime-selected-proof/{suffix}/primary/negative-analysis.log'}
        primary=HERE/'current-runtime-selected-proof'/suffix/'primary'
        entry['post_capture']['test_log']=str((primary/'saved-command.log').relative_to(HERE))
        entry['post_capture']['test_log_sha256']=sha(primary/'saved-command.log')
        entry['post_capture']['test_exit_code']=0
        physical=HERE/'current-runtime-selected-physical-preparation'/suffix/'proof.json'
        require(physical.is_file(), 'Fresh physical preparation proof missing: '+suffix)
        entry['physical_preparation']={'receipt':str(physical.relative_to(HERE)),'sha256':sha(physical)}
        entry['preparation_status']='selected_cpu_offline_compat_saved_proven_physical_unverified'
    old['runtime_manifest_sha256']=current
    old['status']='partial_selected_cpu_proofs_bound_physical_unverified'
    MANIFEST.write_text(json.dumps(old,indent=2)+'\n')
    print(json.dumps({'cases':len(old['cases']),'candidate_proofs':8,
                      'manifest_sha256':sha(MANIFEST),'runtime_manifest_sha256':current}))


if __name__=='__main__':
    main()
