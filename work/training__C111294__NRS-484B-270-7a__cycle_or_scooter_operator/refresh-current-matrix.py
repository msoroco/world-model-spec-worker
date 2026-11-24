"""Run six exact current public fallback chains on bounded CPU workers."""
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
SCRATCH = ROOT / '.runtime-work/c111294-current-v3'
CHECKS = {'actual_analysis', 'native_validation', 'mandatory_observations',
          'lean_decoder', 'render', 'final_decode', 'acquisition_unchanged',
          'derived_outputs_rebuilt', 'four_camera_sources',
          'selected_measurements', 'negative_case_source'}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(case, candidate):
    manifest = HERE / ('v2-' + ('primary' if candidate == 'primary' else 'fallbacks') + '-' + case + '-manifest.json')
    case_id = HERE.name + '__' + case
    root = SCRATCH / (case + '-' + candidate)
    root.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1',
               SCENARIO_PIPELINE_OUTPUT_ROOT=str(root), TMPDIR=str(root))
    common = ['--manifest', str(manifest), '--case', case_id,
              '--candidate', candidate]
    commands = [
        ('offline', [sys.executable, str(ROOT / 'runtime.py'), 'offline', *common,
                     '--output', str(root / 'offline'), '--python', sys.executable]),
        ('compatibility', [sys.executable, str(ROOT / 'runtime.py'), 'compatibility', *common,
                           '--output', str(root / 'compat'), '--library',
                           str(ROOT / 'runtime/library'), '--validator',
                           str(ROOT / '.runtime-work/c111294-current/decoder/.lake/build/bin/adapterCheck')]),
        ('process-saved', [sys.executable, str(ROOT / 'runtime.py'), 'process-saved',
                           '--manifest', str(manifest), '--case', case_id,
                           '--attempt', str(root / 'compat'), '--output', str(root / 'saved'),
                           '--library', str(ROOT / 'runtime/library'), '--validator',
                           str(ROOT / '.runtime-work/c111294-current/decoder/.lake/build/bin/adapterCheck')]),
    ]
    for stage, command in commands:
        log = root / (stage + '.log')
        with log.open('w') as stream:
            completed = subprocess.run(command, cwd=ROOT, env=env, stdout=stream,
                                       stderr=subprocess.STDOUT, timeout=600)
        if completed.returncode:
            return {'case': case, 'candidate': candidate, 'passed': False,
                    'stage': stage, 'exit_code': completed.returncode,
                    'tail': log.read_text()[-1500:]}
    compat = json.loads((root / 'compat/compatibility.json').read_text())
    saved = json.loads((root / 'saved/v0001/processing.json').read_text())
    assert compat['passed'] and CHECKS <= set(compat['checks'])
    assert compat['negative_removed'] == 'interaction.json'
    assert saved['passed'] and saved['recorded_only'] and saved['originals_preserved']
    assert saved['timestamp_joins']['frames'] == 600 and saved['final_video_checks']['passed']
    assert not saved['physical_acceptance_claimed'] and not saved['legal_acceptance_claimed']
    proof = (HERE / 'v2-primary' / case / 'proofs') if candidate == 'primary' else (HERE / 'v2-fallbacks' / case / candidate / 'proofs')
    proof.mkdir(parents=True, exist_ok=True)
    for source, target in ((root / 'offline/offline.log', 'offline.log'),
                           (root / 'compat/compatibility.json', 'compatibility.json'),
                           (root / 'compat/compatibility-analysis.log', 'analysis.log'),
                           (root / 'compat/negative-analysis.log', 'negative.log'),
                           (root / 'compat/candidate-selection.json', 'candidate-selection.json'),
                           (root / 'saved/v0001/processing.json', 'processing.json')):
        shutil.copyfile(source, proof / target)
        assert (proof / target).stat().st_size <= 2 * 1024 * 1024
    return {'case': case, 'candidate': candidate, 'passed': True,
            'manifest_sha256': sha(manifest), 'compatibility_sha256': sha(proof / 'compatibility.json'),
            'processing_sha256': sha(proof / 'processing.json'), 'frames': 600}


def main():
    jobs = [(case, candidate) for case in ('witness_1', 'witness_2')
            for candidate in ('primary', 'fallback1', 'fallback2', 'fallback3')]
    rows = []
    with ThreadPoolExecutor(max_workers=2) as pool:
        pending = {pool.submit(run, *job): job for job in jobs}
        for future in as_completed(pending):
            case, candidate = pending[future]
            try:
                row = future.result()
            except Exception as error:
                row = {'case': case, 'candidate': candidate, 'passed': False,
                       'stage': 'orchestration', 'error': repr(error)}
            rows.append(row)
            print(case, candidate, 'PASS' if row['passed'] else 'FAIL', flush=True)
    path = HERE / 'current-matrix-summary.json'
    path.write_text(json.dumps({'format': 'c111294-current-eight-chain-matrix',
        'results': sorted(rows, key=lambda row: (row['case'], row['candidate']))}, indent=2) + '\n')
    if any(not row['passed'] for row in rows):
        raise SystemExit(1)


if __name__ == '__main__':
    main()
