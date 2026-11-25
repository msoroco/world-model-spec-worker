"""Prove selected current-runtime compatibility and recorded-only processing."""
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
MANIFEST = HERE / 'selected-probe-manifest.json'
RETURN = HERE / 'selected-public'
SCRATCH = ROOT / '.runtime-work' / 'c3823554001-selected-public-through-v2'
VALIDATOR = ROOT / '.runtime-work/c229398-pinned-decoder/.lake/build/bin/adapterCheck'
CASES = ('witness_1', 'witness_2', 'extreme_right_1', 'extreme_right_2')
CANDIDATES = ('primary', 'fallback1', 'fallback2')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_clean(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('\n'.join(line.rstrip() for line in content.splitlines()).rstrip() + '\n')
    if path.stat().st_size > 2 * 1024 * 1024:
        raise ValueError('Returned public file exceeds 2 MiB: ' + str(path))


def command(argv, log, env):
    run = subprocess.run(argv, cwd=ROOT, env=env, capture_output=True,
                         text=True, timeout=1800)
    write_clean(log, run.stdout + run.stderr)
    if run.returncode:
        raise RuntimeError(f'{log} exit {run.returncode}')
    return ' '.join(argv)


def one(case, candidate):
    key = case + '-' + candidate
    case_id = HERE.name + '__' + case
    attempt = SCRATCH / 'attempt' / key
    saved = SCRATCH / 'saved' / key
    env = dict(os.environ, TMPDIR=str(SCRATCH), MPLCONFIGDIR=str(SCRATCH),
               PYTHONDONTWRITEBYTECODE='1',
               SCENARIO_PIPELINE_OUTPUT_ROOT=str(SCRATCH / 'pipeline'))
    common = ['--library', str(ROOT / 'runtime/library'), '--validator', str(VALIDATOR)]
    base = ['--manifest', str(MANIFEST), '--case', case_id]
    compat_log = RETURN / (key + '-compat.log')
    saved_log = RETURN / (key + '-saved.log')
    compat_command = command([sys.executable, str(ROOT / 'runtime.py'), 'compatibility',
                              *base, '--candidate', candidate,
                              '--output', str(attempt), *common], compat_log, env)
    receipt = json.loads((attempt / 'compatibility.json').read_text())
    if not receipt['passed'] or receipt['negative_removed'] != 'native_samples.jsonl':
        raise ValueError('Selected positive or case-source negative failed')
    saved_command = command([sys.executable, str(ROOT / 'runtime.py'), 'process-saved',
                             *base, '--attempt', str(attempt), '--output', str(saved),
                             *common], saved_log, env)
    processing = json.loads((saved / 'v0001/processing.json').read_text())
    if not (processing['passed'] and processing['recorded_only'] and
            processing['timestamp_joins']['frames'] == 480 and
            processing['final_video_checks']['frames'] == 480 and
            processing['missing_evidence'] is False and
            processing['physical_acceptance_claimed'] is False):
        raise ValueError('Selected recorded-only saved processing failed')
    sources = [(attempt / 'compatibility.json', key + '-compatibility.json'),
               (attempt / 'compatibility-analysis.log', key + '-analysis.log'),
               (attempt / 'negative-analysis.log', key + '-negative.log'),
               (saved / 'v0001/processing.json', key + '-processing.json')]
    for source, name in sources:
        write_clean(RETURN / name, source.read_text())
    return {'case_id': case_id, 'candidate': candidate,
            'construction_sha256': receipt['construction_sha256'],
            'compatibility_command': compat_command, 'saved_command': saved_command,
            'compatibility_receipt': 'selected-public/' + key + '-compatibility.json',
            'compatibility_receipt_sha256': sha(RETURN / (key + '-compatibility.json')),
            'analysis_log_sha256': sha(RETURN / (key + '-analysis.log')),
            'negative_log_sha256': sha(RETURN / (key + '-negative.log')),
            'saved_processing_receipt': 'selected-public/' + key + '-processing.json',
            'saved_processing_sha256': sha(RETURN / (key + '-processing.json')),
            'compatibility_log_sha256': sha(compat_log),
            'saved_log_sha256': sha(saved_log),
            'physical_or_legal_acceptance_claimed': False}


def main():
    RETURN.mkdir(exist_ok=True)
    SCRATCH.mkdir(parents=True, exist_ok=True)
    pairs = [(case, candidate) for case in CASES for candidate in CANDIDATES]
    records = []
    with ThreadPoolExecutor(max_workers=3) as pool:
        futures = {pool.submit(one, *pair): pair for pair in pairs}
        for future in as_completed(futures):
            case, candidate = futures[future]
            records.append(future.result())
            print(case, candidate, 'passed', flush=True)
    report = {'format': 'c382355-400-1-selected-current-public-proof',
              'manifest_sha256': sha(MANIFEST),
              'records': sorted(records, key=lambda item: (item['case_id'], item['candidate'])),
              'physical_or_legal_acceptance_claimed': False}
    write_clean(RETURN / 'proof.json', json.dumps(report, indent=2))
    print('proof_sha256', sha(RETURN / 'proof.json'))


if __name__ == '__main__':
    main()
