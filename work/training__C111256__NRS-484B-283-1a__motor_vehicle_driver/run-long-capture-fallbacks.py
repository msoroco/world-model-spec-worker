"""Exercise twelve unselected 600-frame fallbacks through pinned public CPU paths."""
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SCRATCH = ROOT / '.runtime-work/c111256-fallbacks'
CASES = ('witness_1', 'witness_2', 'exception_1_1', 'exception_1_2')
CANDIDATES = ('fallback1', 'fallback2', 'fallback3')
CHECKS = {'actual_analysis', 'native_validation', 'mandatory_observations',
          'lean_decoder', 'render', 'final_decode', 'acquisition_unchanged',
          'derived_outputs_rebuilt', 'four_camera_sources',
          'selected_measurements', 'negative_case_source'}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(case, candidate):
    name = case + '-' + candidate
    manifest = HERE / f'long-capture-fallbacks-{case}-manifest.json'
    case_id = HERE.name + '__' + case
    scratch = SCRATCH / name
    scratch.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ)
    env['PYTHONDONTWRITEBYTECODE'] = '1'
    env['SCENARIO_PIPELINE_OUTPUT_ROOT'] = str(scratch)
    env['TMPDIR'] = str(scratch)
    offline = scratch / 'offline'
    compat = scratch / 'compat'
    saved = scratch / 'saved'
    common = ['--manifest', str(manifest), '--case', case_id,
              '--candidate', candidate]
    commands = [
        ('offline', [sys.executable, str(ROOT / 'runtime.py'), 'offline', *common,
                     '--output', str(offline), '--python', sys.executable]),
        ('compatibility', [sys.executable, str(ROOT / 'runtime.py'), 'compatibility',
                           *common, '--output', str(compat), '--library',
                           str(ROOT / 'runtime/pipeline/library'), '--validator',
                           str(ROOT / '.runtime-work/c10316-current-decoder/.lake/build/bin/adapterCheck')]),
        ('process-saved', [sys.executable, str(ROOT / 'runtime.py'), 'process-saved',
                           '--manifest', str(manifest), '--case', case_id,
                           '--attempt', str(compat), '--output', str(saved),
                           '--library', str(ROOT / 'runtime/pipeline/library'),
                           '--validator', str(ROOT / '.runtime-work/c10316-current-decoder/.lake/build/bin/adapterCheck')]),
    ]
    command_log = scratch / 'command.log'
    with command_log.open('w') as stream:
        for stage, command in commands:
            stream.write('STAGE ' + stage + '\n')
            stream.flush()
            completed = subprocess.run(command, cwd=ROOT, env=env,
                                       stdout=stream, stderr=subprocess.STDOUT,
                                       timeout=600)
            if completed.returncode:
                return {'case': case, 'candidate': candidate, 'passed': False,
                        'stage': stage, 'exit_code': completed.returncode,
                        'error_tail': '\n'.join(command_log.read_text().splitlines()[-15:])}
    receipt = json.loads((compat / 'compatibility.json').read_text())
    processing_path = saved / 'v0001/processing.json'
    processing = json.loads(processing_path.read_text())
    construction = next(item for item in json.loads(manifest.read_text())['cases'][0]['candidates']
                        if item['id'] == candidate)
    assert receipt['passed'] and CHECKS <= set(receipt['checks'])
    assert receipt['case_id'] == case_id and receipt['candidate_id'] == candidate
    assert receipt['construction_sha256'] == construction['construction_sha256']
    assert receipt['negative_removed'] == 'road_geometry.json'
    assert processing['passed'] and not processing['missing_evidence']
    assert processing['candidate_id'] == candidate and processing['originals_preserved']
    assert processing['timestamp_joins']['frames'] == 600
    assert processing['final_video_checks']['passed']
    assert not processing['physical_acceptance_claimed']
    return {'case': case, 'candidate': candidate, 'passed': True,
            'manifest_sha256': sha(manifest),
            'construction_sha256': construction['construction_sha256'],
            'offline_log_sha256': sha(offline / 'offline.log'),
            'compatibility_sha256': sha(compat / 'compatibility.json'),
            'saved_sha256': sha(processing_path),
            'frames': 600, 'negative_removed': 'road_geometry.json',
            'originals_preserved': True, 'selected': False,
            'physical_observation': False}


def main():
    SCRATCH.mkdir(parents=True, exist_ok=True)
    results = []
    with ThreadPoolExecutor(max_workers=2) as pool:
        pending = {pool.submit(run, case, candidate): (case, candidate)
                   for case in CASES for candidate in CANDIDATES}
        for future in as_completed(pending):
            case, candidate = pending[future]
            try:
                result = future.result()
            except Exception as error:
                result = {'case': case, 'candidate': candidate, 'passed': False,
                          'stage': 'orchestration', 'error': repr(error)}
            results.append(result)
            target = HERE / 'long-capture-fallbacks' / 'matrix-summary.json'
            target.write_text(json.dumps({'format': 'c111256-unselected-600-frame-fallback-matrix',
                                          'results': sorted(results,
                                                            key=lambda row: (row['case'], row['candidate']))},
                                         indent=2) + '\n')
            print(case, candidate, 'PASS' if result['passed'] else 'FAIL', flush=True)
    if any(not result['passed'] for result in results):
        raise SystemExit(1)


if __name__ == '__main__':
    main()
