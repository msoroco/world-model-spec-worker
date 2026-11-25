"""Reproduce paragraph (d) selected draft offline and saved-source CPU checks."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent
NATIVE = HERE.parent
CASE = NATIVE.parent
ROOT = CASE.parents[1]
MANIFEST = HERE / 'manifest.json'
sys.path.insert(0, str(NATIVE))
import prove_current_primary_saved
import prove_current_contrast_saved


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def run():
    scratch = Path(os.environ.get('TMPDIR', '')).resolve()
    if ROOT / '.runtime-work' not in scratch.parents:
        raise ValueError('TMPDIR must be under .runtime-work')
    env = dict(os.environ)
    env['PYTHONPATH'] = str(ROOT / 'runtime/scenario_pipeline')
    receipts = []
    with tempfile.TemporaryDirectory(dir=scratch, prefix='selected-d-') as name:
        base = Path(name)
        for suffix, proof in [('witness_1', prove_current_primary_saved),
                              ('witness_2', prove_current_contrast_saved)]:
            case_id = CASE.name + '__' + suffix
            offline = base / (suffix + '-offline')
            command = [str(ROOT / '.venv-cpu/bin/python'),
                str(ROOT / 'runtime.py'), 'offline', '--manifest', str(MANIFEST),
                '--case', case_id, '--output', str(offline)]
            result = subprocess.run(command, cwd=ROOT, env=env,
                                    capture_output=True, text=True, timeout=300)
            if result.returncode:
                raise RuntimeError('Selected draft offline failed: ' + result.stdout + result.stderr)
            attempt = base / (suffix + '-positive')
            subprocess.run([str(ROOT / '.venv-cpu/bin/python'),
                str(ROOT / 'runtime.py'), 'materialize', '--manifest', str(MANIFEST),
                '--case', case_id, '--output', str(attempt)],
                cwd=ROOT, env=env, capture_output=True, text=True,
                check=True, timeout=300)
            proof.BUNDLE = attempt
            proof.fixture(attempt)
            finalize = [str(ROOT / '.venv-cpu/bin/python'),
                str(attempt / 'finalize.py'), '--attempt', str(attempt),
                '--output', str(attempt / 'analysis-report.json')]
            positive = subprocess.run(finalize, cwd=attempt, env=env,
                                      capture_output=True, text=True, timeout=300)
            if positive.returncode:
                raise RuntimeError('Saved positive failed: ' + positive.stdout + positive.stderr)
            analysis = json.loads((attempt / 'analysis-report.json').read_text())
            native = json.loads((attempt / 'result.json').read_text())
            if (analysis.get('physical_or_legal_acceptance') is not False or
                    native.get('accepted') is not False or
                    native.get('provenance_kind') != 'synthetic_local_diagnostic'):
                raise ValueError('Diagnostic finalizer overclaimed acceptance')
            negative_attempt = base / (suffix + '-negative')
            shutil.copytree(attempt, negative_attempt)
            (negative_attempt / 'source-review.json').unlink()
            negative = subprocess.run([str(ROOT / '.venv-cpu/bin/python'),
                str(negative_attempt / 'finalize.py'), '--attempt',
                str(negative_attempt), '--output',
                str(negative_attempt / 'negative-report.json')],
                cwd=negative_attempt, env=env,
                capture_output=True, text=True, timeout=300)
            if (negative.returncode == 0 or
                    'Missing required source: source-review.json' not in negative.stderr):
                raise ValueError('Missing-source negative did not fail')
            log = HERE / (suffix + '-offline.log')
            log.write_text((offline / 'offline.log').read_text().rstrip() + '\n')
            receipts.append({'case_id': case_id,
                'construction_sha256': next(c['construction_sha256']
                    for c in json.loads(MANIFEST.read_text())['cases']
                    if c['case_id'] == case_id),
                'offline_log': log.name, 'offline_log_sha256': sha(log),
                'analysis_report_sha256': sha(attempt / 'analysis-report.json'),
                'native_result_sha256': sha(attempt / 'result.json'),
                'positive_exit_code': positive.returncode,
                'negative_exit_code': negative.returncode,
                'negative_error': 'Missing required source: source-review.json',
                'synthetic_diagnostic': True, 'original_native_observed': False,
                'delivery_ready': False})
    record = {'format': 'c146314-paragraph-d-selected-draft-cpu-proof-v1',
        'manifest_sha256': sha(MANIFEST), 'cases': receipts,
        'scope': 'source-shape/offline diagnostic only; no CARLA execution'}
    destination = HERE / 'selected-draft-proof.json'
    destination.write_text(json.dumps(record, indent=2, sort_keys=True) + '\n')
    return {'proof_sha256': sha(destination), 'cases': len(receipts)}


if __name__ == '__main__':
    print(json.dumps(run(), sort_keys=True))
