"""Run the six exact candidate offline and current public compatibility checks."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
MANIFEST = HERE / 'current-v2-candidate-manifest.json'
VALIDATOR = ROOT / '.runtime-work/c110919-owner104/decoder/.lake/build/bin/adapterCheck'
SCRATCH = ROOT / '.runtime-work/c110919-8c-owner104'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(suffix, candidate):
    if suffix not in ('probe_a', 'probe_b') or candidate not in ('primary', 'fallback1', 'fallback2'):
        raise ValueError('Unknown exact case/candidate')
    case_id = HERE.name + '__' + suffix
    target = HERE / 'current-v2-candidates' / suffix / candidate
    target.mkdir(parents=True, exist_ok=True)
    base = SCRATCH / f'proof-{suffix}-{candidate}'
    base.mkdir(parents=True, exist_ok=True)
    commands = [
        ('offline', [sys.executable, str(ROOT / 'runtime.py'), 'offline', '--manifest', str(MANIFEST),
                     '--case', case_id, '--candidate', candidate, '--output', str(base / 'offline')]),
        ('compatibility', [sys.executable, str(ROOT / 'runtime.py'), 'compatibility', '--manifest', str(MANIFEST),
                           '--case', case_id, '--candidate', candidate, '--output', str(base / 'compatibility'),
                           '--library', str(ROOT / 'runtime/library'), '--validator', str(VALIDATOR)])]
    for name, command in commands:
        log = target / f'{name}-command.log'
        if name == 'compatibility' and (base / 'compatibility/compatibility.json').is_file():
            continue
        executed = subprocess.run(command, text=True, stdout=subprocess.PIPE,
                                  stderr=subprocess.STDOUT, timeout=1800)
        log.write_text(executed.stdout)
        if executed.returncode:
            raise RuntimeError(f'{suffix}/{candidate} {name} exit {executed.returncode}: {log}')
    result = base / 'compatibility'
    compatibility = json.loads((result / 'compatibility.json').read_text())
    if compatibility.get('passed') is not True or compatibility.get('candidate_id') != candidate:
        raise ValueError('Current public compatibility did not pass')
    for name in ('compatibility.json', 'compatibility-analysis.log', 'negative-analysis.log'):
        shutil.copyfile(result / name, target / name)
    receipt = {'case_id': case_id, 'candidate_id': candidate, 'construction_sha256':
               compatibility['construction_sha256'], 'compatibility_sha256': sha(target / 'compatibility.json'),
               'negative_log_sha256': sha(target / 'negative-analysis.log'),
               'offline_log_sha256': sha(target / 'offline-command.log'), 'passed': True}
    (target / 'proof.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps({'case': suffix, 'candidate': candidate, 'proof_sha256': sha(target / 'proof.json')}), flush=True)


if __name__ == '__main__':
    os.environ.setdefault('SCENARIO_PIPELINE_OUTPUT_ROOT', str(SCRATCH))
    run(sys.argv[1], sys.argv[2])
