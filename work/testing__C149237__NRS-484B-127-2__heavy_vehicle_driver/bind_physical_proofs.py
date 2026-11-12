"""Run and bind three motion outcomes and Native lifecycle for each truck case."""
import hashlib
import json
import subprocess
from pathlib import Path

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
MANIFEST=f'work/{HERE.name}/execution-manifest.json'
KINDS=('complete_motion','incomplete_motion','missing_evidence')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def run(case,suffix,kind):
    directory=HERE/'physical-proofs'/suffix
    directory.mkdir(parents=True,exist_ok=True)
    relative=f'physical-proofs/{suffix}/{kind}'
    command=(f'.venv-cpu/bin/python work/{HERE.name}/physical_fixture_proof.py '
             f'--manifest {MANIFEST} --case {case} --kind {kind} '
             f'--output work/{HERE.name}/{relative}.json')
    log=HERE/(relative+'.log')
    with log.open('w') as stream:
        result=subprocess.run(command.split(),cwd=ROOT,stdout=stream,stderr=subprocess.STDOUT)
    if result.returncode:
        raise ValueError('Physical fixture failed: '+case+' '+kind+'; see '+str(log))
    report=HERE/(relative+'.json')
    return {'kind':kind,'command':command,'exit_code':0,
            'log':relative+'.log','log_sha256':sha(log),
            'result':relative+'.json','result_sha256':sha(report)}


def main():
    path=HERE/'execution-manifest.json'
    manifest=json.loads(path.read_text())
    for entry in manifest['cases']:
        case=entry['case_id'];suffix=case.split('__')[-1]
        fixtures=[run(case,suffix,kind) for kind in KINDS]
        life=run(case,suffix,'lifecycle')
        lifecycle={'events':['capture_finished','encoders_closed','restoration_verified',
                             'native_exit','owner_released','saved_processing_started'],
                   'exit_code':0,'command':life['command'],
                   'log':life['log'],'log_sha256':life['log_sha256'],
                   'result':life['result'],'result_sha256':life['result_sha256']}
        receipt={'format':'worker-physical-preparation-proof',
                 'case_id':case,'construction_sha256':entry['construction_sha256'],
                 'diagnostic_fixture':True,'physical_acceptance_claimed':False,
                 'fixtures':fixtures,'lifecycle':lifecycle}
        receipt_path=HERE/'physical-proofs'/suffix/'receipt.json'
        receipt_path.write_text(json.dumps(receipt,indent=2)+'\n')
        entry['physical_preparation']={
            'receipt':str(receipt_path.relative_to(HERE)),
            'sha256':sha(receipt_path)}
        print('passed',suffix,flush=True)
    path.write_text(json.dumps(manifest,indent=2)+'\n')
    print(json.dumps({'cases':len(manifest['cases']),
                      'physical_fixture_proofs_bound':True,
                      'real_carla_motion_claimed':False},sort_keys=True))


if __name__=='__main__':
    main()
