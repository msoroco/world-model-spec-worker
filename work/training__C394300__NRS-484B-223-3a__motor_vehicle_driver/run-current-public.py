"""Run exact selected source compatibility and saved-only CPU chains."""
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
MANIFEST = HERE / 'current-diagnostic-manifest.json'
RETURN = HERE / 'current-public'
SCRATCH = ROOT / '.runtime-work/c394300-current'
VALIDATOR = ROOT / '.runtime-work/c229398-pinned-decoder/.lake/build/bin/adapterCheck'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def command(argv, log, env):
    with log.open('w') as output:
        result = subprocess.run(argv, cwd=ROOT, env=env, stdout=output,
                                stderr=subprocess.STDOUT, timeout=1500)
    if result.returncode:
        raise RuntimeError(f'{log} exit {result.returncode}')


def one(case_suffix, candidate):
    key = case_suffix + '-' + candidate
    case = HERE.name + '__' + case_suffix
    attempt = SCRATCH / 'output' / key
    saved = SCRATCH / 'saved' / key
    temp = SCRATCH / 'tmp'
    temp.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ, TMPDIR=str(temp), MPLCONFIGDIR=str(temp),
               PYTHONDONTWRITEBYTECODE='1',
               SCENARIO_PIPELINE_OUTPUT_ROOT=str(SCRATCH / 'pipeline'))
    base = ['--manifest', str(MANIFEST), '--case', case]
    common = ['--library', str(ROOT / 'runtime/library'),
              '--validator', str(VALIDATOR)]
    compat_log = RETURN / (key + '-compat.log')
    saved_log = RETURN / (key + '-saved.log')
    command([sys.executable, str(ROOT / 'runtime.py'), 'compatibility',
             *base, '--candidate', candidate, '--output', str(attempt), *common],
            compat_log, env)
    receipt = json.loads((attempt / 'compatibility.json').read_text())
    if not receipt['passed'] or receipt['negative_removed'] != 'declared_purpose.json':
        raise ValueError('Current public or missing-purpose negative failed')
    command([sys.executable, str(ROOT / 'runtime.py'), 'process-saved',
             *base, '--attempt', str(attempt), '--output', str(saved), *common],
            saved_log, env)
    processing = json.loads((saved / 'v0001/processing.json').read_text())
    if not (processing['passed'] and processing['recorded_only'] and
            processing['timestamp_joins']['frames'] == 480 and
            processing['final_video_checks']['frames'] == 480 and
            processing['physical_acceptance_claimed'] is False):
        raise ValueError('Current recorded-only saved processing failed')
    for source, target in ((attempt / 'compatibility.json', key + '-compatibility.json'),
                           (attempt / 'compatibility-analysis.log', key + '-analysis.log'),
                           (attempt / 'negative-analysis.log', key + '-negative.log'),
                           (saved / 'v0001/processing.json', key + '-processing.json')):
        shutil.copyfile(source, RETURN / target)
    return {'case_id': case, 'candidate': candidate,
            'construction_sha256': receipt['construction_sha256'],
            'compatibility_receipt': (RETURN / (key + '-compatibility.json')).relative_to(HERE).as_posix(),
            'compatibility_receipt_sha256': sha(attempt / 'compatibility.json'),
            'analysis_log_sha256': sha(attempt / 'compatibility-analysis.log'),
            'negative_log_sha256': sha(attempt / 'negative-analysis.log'),
            'saved_processing_receipt': (RETURN / (key + '-processing.json')).relative_to(HERE).as_posix(),
            'saved_processing_sha256': sha(saved / 'v0001/processing.json'),
            'compatibility_log_sha256': sha(compat_log),
            'saved_log_sha256': sha(saved_log),
            'physical_or_legal_acceptance_claimed': False}


def main():
    RETURN.mkdir(exist_ok=True)
    combinations = [(case, candidate)
                    for case in ('controlled_1', 'controlled_2')
                    for candidate in ('primary', 'fallback1', 'fallback3')
                    if (case, candidate) != ('controlled_1', 'primary')]
    results = []
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = {pool.submit(one, *pair): pair for pair in combinations}
        for future in as_completed(futures):
            pair = futures[future]
            result = future.result()
            results.append(result)
            print(*pair, 'passed', flush=True)
    report = {'format': 'c394300-current-public-source-cpu-proof',
              'manifest_sha256': sha(MANIFEST), 'records': sorted(results,
              key=lambda item: (item['case_id'], item['candidate'])),
              'physical_or_legal_acceptance_claimed': False}
    (RETURN / 'additional-proof.json').write_text(json.dumps(report, indent=2) + '\n')
    print('proof_sha256', sha(RETURN / 'additional-proof.json'))


if __name__ == '__main__':
    main()
