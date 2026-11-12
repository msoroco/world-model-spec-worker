"""Retain CPU outcome-branch tests and a current synthetic rejection."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess


HERE=Path(__file__).resolve().parent
REPO=HERE.parents[1]
PYTHON=REPO/'.venv-cpu/bin/python'


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    tests=[str(PYTHON),'-m','unittest','discover','-s',str(HERE/'tests'),
           '-p','test_physical_fixture_audit.py','-v']
    run=subprocess.run(tests,cwd=REPO,capture_output=True,text=True)
    (HERE/'physical-fixture-cpu-tests.log').write_text(run.stdout+run.stderr)
    if run.returncode:raise RuntimeError('Physical fixture audit CPU tests failed')
    selected=json.loads((HERE/'execution-manifest.json').read_text())['cases'][0]
    attempt=REPO/'.runtime-work/c10014-update021-reference-primary-compat'
    saved=REPO/'.runtime-work/c10014-update021-reference-primary-saved/v0001'
    negative=[str(PYTHON),str(HERE/'physical_fixture_audit.py'),
              '--attempt',str(attempt),'--owner-receipt',str(attempt/'owner-release.json'),
              '--processing',str(saved/'processing.json'),
              '--kind','complete_motion','--case',selected['case_id'],
              '--construction-sha256',selected['construction_sha256']]
    rejected=subprocess.run(negative,cwd=REPO,capture_output=True,text=True)
    (HERE/'physical-fixture-audit-negative.log').write_text(rejected.stdout+rejected.stderr)
    expected='Synthetic or accepted result cannot prove Native physical outcome'
    if rejected.returncode==0 or expected not in rejected.stdout+rejected.stderr:
        raise RuntimeError('Synthetic selected saved result passed physical outcome audit')
    proof={'format':'c10014-physical-fixture-audit-cpu-proof-v1',
           'script':'physical_fixture_audit.py','script_sha256':sha(HERE/'physical_fixture_audit.py'),
           'tests_command':' '.join(tests),'tests_exit_code':0,
           'tests_log':'physical-fixture-cpu-tests.log',
           'tests_log_sha256':sha(HERE/'physical-fixture-cpu-tests.log'),
           'negative_command':' '.join(negative),'negative_exit_code':rejected.returncode,
           'negative_expected_error':expected,
           'negative_log':'physical-fixture-audit-negative.log',
           'negative_log_sha256':sha(HERE/'physical-fixture-audit-negative.log'),
           'original_native_outcome_proven':False,
           'complete_physical_preparation_proven':False}
    (HERE/'physical-fixture-audit-cpu-proof.json').write_text(json.dumps(proof,indent=2)+'\n')
    print(json.dumps({'tests':2,'synthetic_rejected':True,
                      'proof_sha256':sha(HERE/'physical-fixture-audit-cpu-proof.json')}))


if __name__=='__main__':main()
