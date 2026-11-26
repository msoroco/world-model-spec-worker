"""Refresh current-hash selected and fallback CPU receipts without Native capture."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SCRATCH = ROOT / '.runtime-work/c376609-owner-nov26'
VALIDATOR = ROOT / '.runtime-work/c110969-decoder/.lake/build/bin/adapterCheck'
VERSION = 'v6'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def clean(path, data):
    path.write_text(data.rstrip() + '\n' if data.strip() else '')


def execute(command, log):
    env = dict(os.environ, SCENARIO_PIPELINE_OUTPUT_ROOT=str(SCRATCH / 'output'),
               TMPDIR=str(SCRATCH / 'tmp'), PYTHONDONTWRITEBYTECODE='1')
    result = subprocess.run(command, cwd=ROOT, env=env, text=True,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    clean(log, result.stdout)
    if result.returncode:
        raise ValueError('selected proof failed: ' + log.name + ': ' + result.stdout[-1000:])
    return json.loads(result.stdout)


def run():
    (SCRATCH / 'output').mkdir(parents=True, exist_ok=True)
    (SCRATCH / 'tmp').mkdir(parents=True, exist_ok=True)
    if not VALIDATOR.is_file():
        raise ValueError('pinned Lean adapter validator missing')
    manifest = json.loads((HERE / 'execution-manifest.json').read_text())
    draft = json.loads(json.dumps(manifest))
    for entry in draft['cases']:
        for key in ('offline', 'compatibility', 'negative', 'post_capture'):
            entry.pop(key, None)
    draft_path = HERE / 'execution-manifest.proof-draft.json'
    draft_path.write_text(json.dumps(draft, indent=2) + '\n')
    count = 0
    for entry in manifest['cases']:
        case = entry['case_id']
        suffix = case.removeprefix(HERE.name + '__')
        for candidate in ('primary', 'fallback1'):
            label = candidate + '-' + suffix
            offline = SCRATCH / ('offline-' + VERSION + '-' + label)
            compatible = SCRATCH / ('compat-' + VERSION + '-' + label)
            saved = SCRATCH / ('saved-' + VERSION + '-' + label)
            if any(path.exists() for path in (offline, compatible, saved)):
                raise ValueError('retain existing proof; choose new VERSION')
            command = [sys.executable, str(ROOT / 'runtime.py'), 'offline', '--manifest', str(draft_path),
                       '--case', case, '--candidate', candidate, '--output', str(offline), '--python', sys.executable]
            log = HERE / ('proof-offline-' + label + '.log')
            receipt = execute(command, log)
            if receipt.get('offline_passed') is not True or receipt.get('simulation_started') is not False:
                raise ValueError('offline receipt is not CPU-only')
            proof = {'command': ' '.join(command), 'exit_code': 0, 'log': log.name,
                     'log_sha256': sha(log), 'construction_sha256':
                     entry['construction_sha256'] if candidate == 'primary' else entry['candidates'][0]['construction_sha256']}
            if candidate == 'primary':
                entry['offline'] = proof
            else:
                entry['candidates'][0]['offline'] = proof
            command = [sys.executable, str(ROOT / 'runtime.py'), 'compatibility', '--manifest', str(draft_path),
                       '--case', case, '--candidate', candidate, '--output', str(compatible),
                       '--library', str(ROOT / 'runtime/library'), '--validator', str(VALIDATOR)]
            execute(command, HERE / ('proof-compat-command-' + label + '.log'))
            for name, target in (('compatibility.json', 'proof-compat-receipt-' + label + '.json'),
                                 ('compatibility-analysis.log', 'proof-compat-analysis-' + label + '.log'),
                                 ('negative-analysis.log', 'proof-compat-negative-' + label + '.log')):
                clean(HERE / target, (compatible / name).read_text())
            receipt_path = HERE / ('proof-compat-receipt-' + label + '.json')
            cr = json.loads(receipt_path.read_text())
            cr['log_sha256'] = sha(HERE / ('proof-compat-analysis-' + label + '.log'))
            cr['negative_log_sha256'] = sha(HERE / ('proof-compat-negative-' + label + '.log'))
            receipt_path.write_text(json.dumps(cr, indent=2) + '\n')
            cp = {'receipt': receipt_path.name, 'sha256': sha(receipt_path),
                  'log': 'proof-compat-analysis-' + label + '.log'}
            np = {'log': 'proof-compat-negative-' + label + '.log'}
            if candidate == 'primary':
                entry['compatibility'], entry['negative'] = cp, np
            else:
                entry['candidates'][0]['compatibility'] = cp
                entry['candidates'][0]['negative'] = np
            command = [sys.executable, str(ROOT / 'runtime.py'), 'process-saved', '--manifest', str(draft_path),
                       '--case', case, '--attempt', str(compatible), '--output', str(saved),
                       '--library', str(ROOT / 'runtime/library'), '--validator', str(VALIDATOR)]
            log = HERE / ('proof-saved-' + label + '.log')
            receipt = execute(command, log)
            if not (receipt.get('passed') is True and receipt.get('recorded_only') is True and
                    receipt.get('originals_preserved') is True):
                raise ValueError('saved replay did not preserve originals')
            post = {'command': ' '.join(command), 'exit_code': 0, 'log': log.name,
                    'log_sha256': sha(log), 'recorded_only': True, 'originals_preserved': True}
            if candidate == 'primary':
                entry['post_capture'] = post
            else:
                entry['candidates'][0]['post_capture'] = post
            count += 1
    (HERE / 'execution-manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    return count


if __name__ == '__main__':
    print('current-hash selected/fallback CPU proof chains:', run())
