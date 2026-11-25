"""Run selected recorded-only processing on a source-hashed CPU diagnostic."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
ASSIGNMENT = HERE.name


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main(suffix, compatibility_version):
    case = ASSIGNMENT + '__' + suffix
    manifest = HERE / 'execution-manifest.json'
    source = ROOT / '.runtime-work' / f'c229397-compatible-{suffix}-{compatibility_version}'
    attempt = ROOT / '.runtime-work' / f'c229397-saved-attempt-{suffix}-proof'
    output = ROOT / '.runtime-work' / f'c229397-saved-{suffix}-proof'
    proof = HERE / 'proofs' / suffix
    proof.mkdir(parents=True, exist_ok=True)
    runtime = [sys.executable, str(ROOT / 'runtime.py')]
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1',
               SCENARIO_PIPELINE_OUTPUT_ROOT=str(ROOT / '.runtime-work'))
    with (proof / 'materialize.log').open('x') as log:
        subprocess.run(runtime + ['materialize', '--manifest', str(manifest),
            '--case', case, '--output', str(attempt)], env=env,
            stdout=log, stderr=subprocess.STDOUT, check=True)
    compatibility = json.loads((source / 'compatibility.json').read_text())
    if not compatibility['passed'] or compatibility['case_id'] != case:
        raise ValueError('Exact compatibility source missing')
    for name, digest in compatibility['fixture_manifest'].items():
        item, target = source / name, attempt / name
        if target.exists():
            raise ValueError('Diagnostic source shadows selected construction: ' + name)
        if not name.endswith('.mkv') and sha(item) != digest:
            raise ValueError('Diagnostic source hash changed: ' + name)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(item, target)
    decoder = ROOT / '.runtime-work/c150129-decoder/.lake/build/bin/adapterCheck'
    with (proof / 'process-saved.log').open('x') as log:
        subprocess.run(runtime + ['process-saved', '--manifest', str(manifest),
            '--case', case, '--attempt', str(attempt), '--output', str(output),
            '--library', str(ROOT / 'runtime/library'), '--validator', str(decoder)],
            env=env, stdout=log, stderr=subprocess.STDOUT, check=True)
    receipt = json.loads((output / 'v0001/processing.json').read_text())
    if (receipt['case_id'] != case or not receipt['passed'] or
            not receipt['recorded_only'] or not receipt['originals_preserved'] or
            receipt['timestamp_joins']['frames'] != 600 or
            receipt['missing_evidence'] or not receipt['final_video_checks']['passed']):
        raise ValueError('Saved-only processing failed selected source checks')
    summary = {'case_id': case, 'passed': True, 'recorded_only': True,
               'source_receipt_sha256': sha(output / 'v0001/processing.json'),
               'process_log_sha256': sha(proof / 'process-saved.log'),
               'frame_count': 600, 'originals_preserved': True,
               'diagnostic_fixture': True, 'physical_acceptance_claimed': False}
    (proof / 'saved-processing-summary.json').write_text(json.dumps(summary, indent=2) + '\n')
    print(json.dumps(summary, sort_keys=True))


if __name__ == '__main__':
    if len(sys.argv) != 3:
        raise SystemExit('usage: prove_saved_processing.py SUFFIX COMPATIBILITY_VERSION')
    main(sys.argv[1], sys.argv[2])
