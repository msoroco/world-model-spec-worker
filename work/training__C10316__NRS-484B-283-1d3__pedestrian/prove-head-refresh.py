"""Replay eight current public and recorded-only CPU chains after head rebind."""

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
RETURN = HERE / 'head-refresh'
SCRATCH = ROOT / '.runtime-work/c10316-head-refresh-v5'
MANIFEST = HERE / 'draft-execution-manifest.json'
VALIDATOR = ROOT / '.runtime-work/c229398-pinned-decoder/.lake/build/bin/adapterCheck'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def run(command, path, env):
    with path.open('w') as log:
        result = subprocess.run(command, cwd=ROOT, env=env, stdout=log,
                                stderr=subprocess.STDOUT, timeout=900)
    if result.returncode:
        raise RuntimeError(f'Exit {result.returncode}: {path}')
    return sha(path)


def main():
    RETURN.mkdir(exist_ok=True)
    (SCRATCH / 'tmp').mkdir(parents=True, exist_ok=True)
    env = dict(os.environ, TMPDIR=str(SCRATCH / 'tmp'),
               SCENARIO_PIPELINE_OUTPUT_ROOT=str(SCRATCH / 'pipeline'),
               PYTHONDONTWRITEBYTECODE='1')
    common = ['--library', str(ROOT / 'runtime/library'),
              '--validator', str(VALIDATOR)]
    records = []
    for suffix in ('controlled_1', 'controlled_2'):
        case = HERE.name + '__' + suffix
        for candidate in ('primary', 'fallback1', 'fallback2', 'fallback3'):
            key = suffix + '-' + candidate
            attempt = SCRATCH / key / 'compat'
            saved = SCRATCH / key / 'saved'
            compat_log = RETURN / (key + '-compat.log')
            saved_log = RETURN / (key + '-saved.log')
            base = ['--manifest', str(MANIFEST), '--case', case]
            c_cmd = [sys.executable, str(ROOT / 'runtime.py'), 'compatibility',
                     *base, '--candidate', candidate, '--output', str(attempt), *common]
            c_sha = run(c_cmd, compat_log, env)
            receipt = json.loads((attempt / 'compatibility.json').read_text())
            if not receipt['passed'] or receipt['negative_removed'] != 'no-countdown-samples.jsonl':
                raise ValueError('Public compatibility or missing-source negative failed')
            s_cmd = [sys.executable, str(ROOT / 'runtime.py'), 'process-saved',
                     *base, '--attempt', str(attempt), '--output', str(saved), *common]
            s_sha = run(s_cmd, saved_log, env)
            processing = json.loads((saved / 'v0001/processing.json').read_text())
            if not (processing['passed'] and processing['recorded_only'] and
                    processing['timestamp_joins']['frames'] == 600 and
                    processing['final_video_checks']['frames'] == 600 and
                    processing['physical_acceptance_claimed'] is False):
                raise ValueError('Recorded-only saved processing failed')
            row = {'case_id': case, 'candidate': candidate,
                   'construction_sha256': receipt['construction_sha256'],
                   'compatibility_log': compat_log.relative_to(HERE).as_posix(),
                   'compatibility_log_sha256': c_sha,
                   'compatibility_receipt_sha256': sha(attempt / 'compatibility.json'),
                   'negative_log_sha256': sha(attempt / 'negative-analysis.log'),
                   'saved_log': saved_log.relative_to(HERE).as_posix(),
                   'saved_log_sha256': s_sha,
                   'saved_receipt_sha256': sha(saved / 'v0001/processing.json'),
                   'source_kind': 'synthetic_scene_request',
                   'physical_signal_observed': False}
            records.append(row)
            print(key, 'passed', flush=True)
    proof = {'format': 'c10316-head-refresh-current-public-cpu-proof',
             'runtime_manifest_sha256': json.loads(MANIFEST.read_text())['runtime_manifest_sha256'],
             'manifest_sha256': sha(MANIFEST), 'records': records,
             'physical_or_legal_acceptance_claimed': False}
    path = RETURN / 'proof.json'
    path.write_text(json.dumps(proof, indent=2) + '\n')
    print('proof_sha256', sha(path), flush=True)


if __name__ == '__main__':
    main()
