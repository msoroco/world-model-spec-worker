"""Run and bind exact CPU proofs for the seven remaining cases' fallbacks."""

import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
MANIFEST = ROOT / 'execution-manifest.json'
VALIDATOR = REPO / '.runtime-work/c101303-decoder-b/.lake/build/bin/adapterCheck'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rel(path):
    return str(path.relative_to(ROOT))


def run(command, log):
    with log.open('w') as stream:
        completed = subprocess.run(command, cwd=REPO, stdout=stream,
                                   stderr=subprocess.STDOUT, check=False)
    if completed.returncode:
        raise ValueError(f'CPU proof exited {completed.returncode}: {" ".join(command)}; see {log}')


def prove():
    manifest = json.loads(MANIFEST.read_text())
    python = str(REPO / '.venv-cpu/bin/python')
    runtime = str(REPO / 'runtime.py')
    for entry in manifest['cases'][1:]:
        case = entry['case_id']
        suffix = case.split('__source_verified_', 1)[1]
        folder = ROOT / 'cases' / ('source_verified_' + suffix)
        for candidate in entry['candidates']:
            ident = candidate['id']
            prefix = f'c125714-{suffix}-{ident}'
            offline = REPO / '.runtime-work' / (prefix + '-offline-v1')
            compat = REPO / '.runtime-work' / (prefix + '-compat-v1')
            saved_dir = REPO / '.runtime-work' / (prefix + '-saved-v1')
            offline_log = folder / (ident + '-offline.log')
            compat_log = folder / (ident + '-compatibility.log')
            saved_log = folder / (ident + '-process-saved.log')
            offline_command = [python, runtime, 'offline', '--manifest', str(MANIFEST),
                               '--case', case, '--candidate', ident, '--output', str(offline)]
            compat_command = [python, runtime, 'compatibility', '--manifest', str(MANIFEST),
                              '--case', case, '--candidate', ident, '--output', str(compat),
                              '--library', str(REPO / 'runtime/library'),
                              '--validator', str(VALIDATOR)]
            saved_command = [python, runtime, 'process-saved', '--manifest', str(MANIFEST),
                             '--case', case, '--attempt', str(compat), '--output', str(saved_dir),
                             '--library', str(REPO / 'runtime/library'),
                             '--validator', str(VALIDATOR)]
            if not offline_log.is_file():
                run(offline_command, offline_log)
            if not (compat / 'compatibility.json').is_file():
                run(compat_command, compat_log)
            saved = saved_dir / 'v0001/processing.json'
            if not saved.is_file():
                run(saved_command, saved_log)
            proof = json.loads((compat / 'compatibility.json').read_text())
            processing = json.loads(saved.read_text())
            if (proof.get('passed') is not True or proof.get('case_id') != case or
                    proof.get('candidate_id') != ident or
                    proof.get('construction_sha256') != candidate['construction_sha256'] or
                    processing.get('passed') is not True or
                    processing.get('candidate_id') != ident or
                    processing.get('recorded_only') is not True or
                    processing.get('originals_preserved') is not True or
                    processing.get('physical_acceptance_claimed') is not False or
                    processing.get('legal_acceptance_claimed') is not False):
                raise ValueError('Fallback receipt mismatch: ' + case + ' ' + ident)
            if not all(log.is_file() for log in (offline_log, compat_log, saved_log)):
                raise ValueError('Missing fallback command log: ' + case + ' ' + ident)
            for source, target in (('compatibility.json', f'{ident}-compatibility-receipt.json'),
                                   ('compatibility-analysis.log', f'{ident}-compatibility-analysis.log'),
                                   ('negative-analysis.log', f'{ident}-negative-analysis.log')):
                shutil.copyfile(compat / source, folder / target)
            saved_receipt = folder / f'{ident}-processing-receipt.json'
            shutil.copyfile(saved, saved_receipt)
            candidate['offline'] = {
                'command': ' '.join(str(Path(part).relative_to(REPO)) if part.startswith(str(REPO)) else part
                                    for part in offline_command),
                'exit_code': 0, 'construction_sha256': candidate['construction_sha256'],
                'log': rel(offline_log), 'log_sha256': sha(offline_log)}
            receipt = folder / f'{ident}-compatibility-receipt.json'
            candidate['compatibility'] = {
                'receipt': rel(receipt), 'sha256': sha(receipt),
                'log': rel(folder / f'{ident}-compatibility-analysis.log'),
                'negative_log': rel(folder / f'{ident}-negative-analysis.log')}
            candidate['saved_processing'] = {'receipt': rel(saved_receipt),
                                             'sha256': sha(saved_receipt)}
            MANIFEST.write_text(json.dumps(manifest, indent=2) + '\n')
            print(json.dumps({'case': suffix, 'candidate': ident, 'passed': True}), flush=True)
    print(json.dumps({'passed': True, 'candidate_count': sum(len(e['candidates']) for e in manifest['cases'])}),
          flush=True)


if __name__ == '__main__':
    prove()
