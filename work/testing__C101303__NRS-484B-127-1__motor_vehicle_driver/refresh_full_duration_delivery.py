"""Rerun all eight source-bound 900-frame diagnostic delivery audit fixtures."""
import hashlib
import json
import shlex
import shutil
import subprocess
from pathlib import Path

folder=Path(__file__).resolve().parent
repo=folder.parent.parent
manifest_path=folder/'execution-manifest.json'
manifest=json.loads(manifest_path.read_text())


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def run(args,log):
    log.parent.mkdir(parents=True,exist_ok=True)
    with log.open('w') as out:
        return subprocess.run(args,cwd=repo,stdout=out,stderr=subprocess.STDOUT)


for entry in manifest['cases']:
    case=entry['case_id']
    label=case.rsplit('source_verified_',1)[1]
    proof=entry['delivery_acceptance']
    positive=repo/'.runtime-work/c101303-full-duration'/(label+'-positive-v1')
    negative=repo/'.runtime-work/c101303-full-duration'/(label+'-negative-v1')
    command=[str(repo/'.venv-cpu/bin/python'),str(folder/'delivery_fixture_proof.py'),
             '--case',case,'--output-root',str(positive.relative_to(repo))]
    log=folder/proof['test_log']
    passed=run(command,log)
    if passed.returncode:
        raise ValueError('Full-duration positive diagnostic failed: '+case+'; see '+str(log))
    audit=json.loads((positive/'attempt/diagnostic-audit.json').read_text())
    if (audit.get('frames')!=900 or audit.get('passed') is not False or
            audit.get('software_checks_passed') is not True or
            audit.get('diagnostic_fixture') is not True or
            audit.get('physical_acceptance_claimed') is not False):
        raise ValueError('Diagnostic audit scope/duration mismatch: '+case)
    negative_command=[str(repo/'.venv-cpu/bin/python'),str(folder/'delivery_fixture_proof.py'),
                      '--case',case,'--output-root',str(negative.relative_to(repo)),
                      '--negative-missing-source','--negative-source-root',str(positive.relative_to(repo))]
    negative_log=folder/proof['negative_log']
    rejected=run(negative_command,negative_log)
    if (rejected.returncode==0 or
            proof['negative_expected_error'] not in negative_log.read_text()):
        raise ValueError('Missing-source negative diagnostic failed: '+case)
    shutil.copyfile(positive/'attempt/diagnostic-audit.json',folder/proof['diagnostic_audit'])
    shutil.copyfile(positive/'source-decode.json',folder/proof['diagnostic_decode_receipt'])
    proof.update(command=shlex.join(command),test_exit_code=0,test_log_sha256=sha(log),
                 negative_command=shlex.join(negative_command),negative_exit_code=rejected.returncode,
                 negative_log_sha256=sha(negative_log),
                 diagnostic_audit_sha256=sha(folder/proof['diagnostic_audit']),
                 diagnostic_decode_receipt_sha256=sha(folder/proof['diagnostic_decode_receipt']))
    manifest_path.write_text(json.dumps(manifest,indent=2)+'\n')
    print('900-frame positive and missing-source negative passed',label,flush=True)
