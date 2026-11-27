"""Rerun selected source-bound compatibility on current construction bytes."""
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import uuid

PACKAGE = Path(__file__).resolve().parents[1]
REPO = PACKAGE.parents[1]
MANIFEST = PACKAGE / 'execution-manifest.json'
VALIDATOR = REPO / '.runtime-work/c102372-active-decoder/.lake/build/bin/adapterCheck'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def clean(text):
    lines = [line.rstrip() for line in text.splitlines()]
    while lines and not lines[-1]:
        lines.pop()
    return '\n'.join(lines) + ('\n' if lines else '')


def prove(case, candidate_id):
    suffix = case.split('__')[-1]
    output = REPO / '.runtime-work' / (
        'c146314-compat-' + suffix + '-' + candidate_id + '-'
        + uuid.uuid4().hex[:8])
    command = [sys.executable, str(REPO / 'runtime.py'), 'compatibility',
               '--manifest', str(MANIFEST), '--case', case,
               '--candidate', candidate_id, '--output', str(output),
               '--library', str(REPO / 'runtime/library'),
               '--validator', str(VALIDATOR)]
    env = os.environ.copy()
    env['TMPDIR'] = str(REPO / '.runtime-work')
    env['SCENARIO_PIPELINE_OUTPUT_ROOT'] = str(
        REPO / '.runtime-work/c146314-compat-root')
    result = subprocess.run(command, cwd=REPO, capture_output=True, text=True,
                            timeout=600, env=env)
    if result.returncode:
        raise RuntimeError(suffix + '/' + candidate_id + ': '
                           + result.stdout[-1200:] + result.stderr[-1200:]
                           + '; output=' + str(output))
    receipt = json.loads((output / 'compatibility.json').read_text())
    if not receipt['passed'] or receipt['candidate_id'] != candidate_id:
        raise ValueError('Compatibility receipt incomplete: ' + suffix + '/' + candidate_id)
    return case, candidate_id, output, command


def main():
    manifest = json.loads(MANIFEST.read_text())
    jobs = [(entry['case_id'], ident) for entry in manifest['cases']
            for ident in ['primary'] + [c['id'] for c in entry['candidates']]]
    completed = []
    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = [executor.submit(prove, *job) for job in jobs]
        for future in as_completed(futures):
            completed.append(future.result())
            print('PASS', completed[-1][0].split('__')[-1], completed[-1][1],
                  flush=True)
    by_case = {entry['case_id']: entry for entry in manifest['cases']}
    for case, candidate_id, output, command in completed:
        entry = by_case[case]
        selected = entry if candidate_id == 'primary' else next(
            c for c in entry['candidates'] if c['id'] == candidate_id)
        directory = PACKAGE / 'native/scope-refresh/compat' / case.split('__')[-1] / candidate_id
        directory.mkdir(parents=True, exist_ok=True)
        positive = directory / 'public-analysis.log'
        negative = directory / 'negative-analysis.log'
        receipt_path = directory / 'compatibility.json'
        positive.write_text(clean((output / 'compatibility-analysis.log').read_text()))
        negative.write_text(clean((output / 'negative-analysis.log').read_text()))
        receipt = json.loads((output / 'compatibility.json').read_text())
        receipt['log_sha256'] = sha(positive)
        receipt['negative_log_sha256'] = sha(negative)
        receipt_path.write_text(json.dumps(receipt, indent=2) + '\n')
        spec = {'receipt': str(receipt_path.relative_to(PACKAGE)),
                'sha256': sha(receipt_path),
                'log': str(positive.relative_to(PACKAGE)),
                'negative_log': str(negative.relative_to(PACKAGE))}
        selected['compatibility'] = spec
        if candidate_id == 'primary':
            entry['negative'] = {'log': spec['negative_log']}
    MANIFEST.write_text(json.dumps(manifest, indent=2) + '\n')
    return len(completed)


if __name__ == '__main__':
    print('Current compatibility proofs passed:', main())
