"""Run recorded-only saved processing for current selected short primaries."""
import concurrent.futures
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess

WORK = Path(__file__).resolve().parent
REPO = WORK.parents[1]
SCRATCH = REPO / '.runtime-work/owner150142'
MANIFEST = WORK / 'execution-manifest.json'
VALIDATOR = SCRATCH / 'current-decoder/.lake/build/bin/adapterCheck'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def run(slug):
    case_id = WORK.name + '__' + slug
    base = SCRATCH / 'short-saved-batch' / slug
    attempt = base / 'attempt'
    saved = base / 'result'
    base.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1',
               TMPDIR=str(REPO / '.runtime-work'),
               SCENARIO_PIPELINE_OUTPUT_ROOT=str(base / 'env'))
    prepare = [str(REPO / '.venv-cpu/bin/python'), str(WORK / 'prepare-current-short-saved.py'),
               '--case', slug, '--candidate', 'primary', '--scratch', str(base)]
    process = [str(REPO / '.venv-cpu/bin/python'), str(REPO / 'runtime.py'),
               'process-saved', '--manifest', str(MANIFEST), '--case', case_id,
               '--attempt', str(attempt), '--output', str(saved),
               '--library', str(REPO / 'runtime/library'),
               '--validator', str(VALIDATOR)]
    with (base / 'prepare.log').open('w') as stream:
        first = subprocess.run(prepare, cwd=REPO, env=env, stdout=stream,
                               stderr=subprocess.STDOUT)
    if first.returncode:
        return {'case': slug, 'stage': 'prepare', 'exit_code': first.returncode,
                'scratch_log': str(base / 'prepare.log')}
    with (base / 'process.log').open('w') as stream:
        second = subprocess.run(process, cwd=REPO, env=env, stdout=stream,
                                stderr=subprocess.STDOUT)
    if second.returncode:
        return {'case': slug, 'stage': 'process-saved', 'exit_code': second.returncode,
                'scratch_log': str(base / 'process.log')}
    processing = saved / 'v0001/processing.json'
    result = json.loads(processing.read_text())
    selection = json.loads((attempt / 'candidate-selection.json').read_text())
    if not (result['passed'] is True and result['recorded_only'] is True and
            result['missing_evidence'] is False and
            result['physical_acceptance_claimed'] is False and
            result['legal_acceptance_claimed'] is False and
            selection['case_id'] == case_id and selection['candidate_id'] == 'primary' and
            selection['manifest_sha256'] == sha(MANIFEST)):
        raise ValueError('Saved selected contract failed: ' + slug)
    copied = {}
    for name, source in [('processing', processing),
                         ('final-decode', saved / 'v0001/final-decode.json'),
                         *[(f'source-{i}', saved / f'v0001/source-{i}.json') for i in range(4)]]:
        target = WORK / f'current-{slug}-primary-saved-{name}.json'
        shutil.copyfile(source, target)
        copied[name] = {'path': target.name, 'sha256': sha(target)}
    return {'case': slug, 'exit_code': 0,
            'frames': result['timestamp_joins']['frames'],
            'construction_sha256': selection['construction_sha256'],
            'manifest_sha256': selection['manifest_sha256'],
            'processing': copied,
            'scratch_attempt': str(attempt), 'scratch_result': str(saved),
            'scratch_process_log_sha256': sha(base / 'process.log'),
            'source_kind': 'synthetic_native_sample',
            'physical_acceptance_claimed': False}


def main():
    manifest = json.loads(MANIFEST.read_text())
    slugs = [item['case_id'].rsplit('__', 1)[-1] for item in manifest['cases']
             if item['case_id'].rsplit('__', 1)[-1] in ('reference', 'contrast')
             or item['case_id'].rsplit('__', 1)[-1].startswith(
                 ('ordinary_', 'armored_car_', 'emergency_vehicle_', 'mail_'))]
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        rows = list(pool.map(run, slugs))
    index = {'format': 'c150142-current-short-selected-saved-v1',
             'manifest_sha256': sha(MANIFEST), 'rows': rows,
             'passed': len(rows) == 14 and all(row['exit_code'] == 0 for row in rows),
             'scope': 'recorded-only synthetic CPU diagnostics',
             'original_native_observed': False}
    target = WORK / 'current-short-selected-saved-index.json'
    target.write_text(json.dumps(index, indent=2) + '\n')
    print(json.dumps({'passed': index['passed'], 'count': len(rows),
                      'failed': [row for row in rows if row['exit_code']],
                      'index_sha256': sha(target)}))
    if not index['passed']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
