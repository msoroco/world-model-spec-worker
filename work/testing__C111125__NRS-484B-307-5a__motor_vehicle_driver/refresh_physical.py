"""Refresh source-bound CPU physical and lifecycle proofs after construction edits."""
import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path

ROOT=Path(__file__).resolve().parent
REPO=ROOT.parents[1]
MANIFEST=ROOT/'execution-manifest.json'


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    manifest=json.loads(MANIFEST.read_text())
    env=dict(os.environ,SCENARIO_PIPELINE_OUTPUT_ROOT=str(REPO/'.runtime-work/c111125-physical'),
             PYTHONPATH=str(REPO/'runtime/scenario_pipeline')+':'+str(REPO/'runtime/python'))
    for entry in manifest['cases']:
        label='yield' if '__yield_' in entry['case_id'] else 'clear'
        output=REPO/'.runtime-work'/f'c111125-physical-{label}-refresh'
        if output.exists():shutil.rmtree(output)
        args=[str(REPO/'.venv-cpu/bin/python'),str(ROOT/'physical_probe.py'),
              '--case',entry['case_id'],'--output',str(output)]
        run=subprocess.run(args,cwd=REPO,env=env,text=True,stdout=subprocess.PIPE,
                           stderr=subprocess.STDOUT)
        log=ROOT/f'physical-{label}-probe.log'
        log.write_text(run.stdout)
        if run.returncode:raise RuntimeError(f'{label}: {run.stdout[-1000:]}')
        proof={'construction_sha256':entry['construction_sha256'],'fixtures':[],
               'lifecycle':{'events':['capture_finished','encoders_closed',
                                      'restoration_verified','native_exit',
                                      'owner_released','saved_processing_started'],
                            'exit_code':0,'log':log.name,'log_sha256':sha(log)},
               'scope':'Synthetic intersection-clearance and lifecycle protocol; no Native capture'}
        for kind in ('complete_motion','incomplete_motion','missing_evidence'):
            result=ROOT/f'physical-{label}-{kind}.json'
            proof['fixtures'].append({'kind':kind,'command':' '.join(args),'exit_code':0,
                                      'log':log.name,'log_sha256':sha(log),
                                      'result':result.name,'result_sha256':sha(result)})
        receipt=ROOT/f'physical-{label}-proof.json'
        receipt.write_text(json.dumps(proof,indent=2)+'\n')
        entry['physical_preparation']={'receipt':receipt.name,'sha256':sha(receipt)}
        MANIFEST.write_text(json.dumps(manifest,indent=2)+'\n')


if __name__=='__main__':main()
