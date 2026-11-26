"""Run exact offline and compatibility proofs for source-gated recovery plans."""
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SCRATCH = ROOT / '.runtime-work/c150098'
VALIDATOR = ROOT / '.runtime-work/c233829/decoder/.lake/build/bin/adapterCheck'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def prove(entry):
    case_id = entry['case_id']
    name = case_id.removeprefix(HERE.name + '__')
    candidate = entry['candidates'][0]
    env = dict(os.environ, SCENARIO_PIPELINE_OUTPUT_ROOT=str(SCRATCH / 'output-root'),
               TMPDIR=str(SCRATCH / 'tmp'), PYTHONDONTWRITEBYTECODE='1')
    offline_output = SCRATCH / ('offline-' + name + '-fallback1')
    offline_log = HERE / ('cpu-offline-' + name + '-fallback1.log')
    command = [sys.executable, str(ROOT / 'runtime.py'), 'offline',
        '--manifest', str(HERE / 'execution-manifest.json'), '--case', case_id,
        '--candidate', 'fallback1', '--output', str(offline_output), '--python', sys.executable]
    if not offline_log.is_file():
        result = subprocess.run(command, cwd=ROOT, env=env, capture_output=True,
                                text=True, timeout=600)
        offline_log.write_text((result.stdout + result.stderr).rstrip() + '\n', encoding='utf-8')
        if result.returncode:
            return name, 'offline', result.returncode
    compat_output = SCRATCH / ('compat-' + name + '-fallback1')
    compat_log = SCRATCH / ('compat-' + name + '-fallback1-cli.log')
    if not (compat_output / 'compatibility.json').is_file():
        command = [sys.executable, str(ROOT / 'runtime.py'), 'compatibility',
            '--manifest', str(HERE / 'execution-manifest.json'), '--case', case_id,
            '--candidate', 'fallback1', '--output', str(compat_output),
            '--library', str(ROOT / 'runtime/library'), '--validator', str(VALIDATOR)]
        result = subprocess.run(command, cwd=ROOT, env=env, capture_output=True,
                                text=True, timeout=1200)
        compat_log.write_text((result.stdout + result.stderr).rstrip() + '\n', encoding='utf-8')
        if result.returncode:
            return name, 'compatibility', result.returncode
    return name, 'passed', 0


def main():
    manifest_path = HERE / 'execution-manifest.json'
    manifest = json.loads(manifest_path.read_text())
    with ThreadPoolExecutor(max_workers=3) as pool:
        futures = [pool.submit(prove, entry) for entry in manifest['cases']]
        outcomes = [future.result() for future in as_completed(futures)]
    for name, stage, code in outcomes:
        print(name + ': ' + stage + ' (' + str(code) + ')', flush=True)
    failures = [name + ':' + stage for name, stage, code in outcomes if code]
    if failures:
        raise ValueError('fallback proof failures: ' + ', '.join(failures))
    for entry in manifest['cases']:
        case_id = entry['case_id']
        name = case_id.removeprefix(HERE.name + '__')
        candidate = entry['candidates'][0]
        offline_log = HERE / ('cpu-offline-' + name + '-fallback1.log')
        candidate['offline'] = {'command': '.venv-cpu/bin/python runtime.py offline --manifest '
            + 'work/' + HERE.name + '/execution-manifest.json --case ' + case_id
            + ' --candidate fallback1 --output $OUTPUT --python $CPU_PYTHON',
            'exit_code': 0, 'construction_sha256': candidate['construction_sha256'],
            'log': offline_log.name, 'log_sha256': sha(offline_log)}
        source = SCRATCH / ('compat-' + name + '-fallback1')
        proof = json.loads((source / 'compatibility.json').read_text())
        if (proof.get('passed') is not True or proof.get('case_id') != case_id or
                proof.get('candidate_id') != 'fallback1' or
                proof.get('construction_sha256') != candidate['construction_sha256']):
            raise ValueError('fallback compatibility receipt differs: ' + name)
        receipt = HERE / ('cpu-compat-' + name + '-fallback1-receipt.json')
        analysis = HERE / ('cpu-compat-' + name + '-fallback1-analysis.log')
        negative = HERE / ('cpu-compat-' + name + '-fallback1-negative.log')
        shutil.copyfile(source / 'compatibility.json', receipt)
        shutil.copyfile(source / 'compatibility-analysis.log', analysis)
        shutil.copyfile(source / 'negative-analysis.log', negative)
        candidate['compatibility'] = {'receipt': receipt.name, 'sha256': sha(receipt),
            'log': analysis.name, 'negative_log': negative.name}
    manifest_path.write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()
