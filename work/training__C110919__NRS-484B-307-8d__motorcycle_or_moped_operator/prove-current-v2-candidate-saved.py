"""Replay one exact current-v2 candidate from its public source inventory."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
MANIFEST = HERE / 'current-v2-candidate-manifest.json'
VALIDATOR = ROOT / '.runtime-work/c110919-owner104/decoder/.lake/build/bin/adapterCheck'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(condition, candidate):
    if condition not in ('condition_a', 'condition_b') or candidate not in ('primary', 'fallback1', 'fallback2', 'fallback3'):
        raise ValueError('Unknown exact case or candidate')
    case_id = HERE.name + '__selected_109a5dbc__' + condition
    folder = HERE / 'current-v2-candidates' / condition / candidate
    compatibility = json.loads((folder / 'compatibility.json').read_text())
    manifest = json.loads(MANIFEST.read_text())
    entry = next(item for item in manifest['cases'] if item['case_id'] == case_id)
    selected = entry if candidate == 'primary' else next(item for item in entry['candidates'] if item['id'] == candidate)
    if (compatibility['passed'] is not True or compatibility['candidate_id'] != candidate
            or compatibility['construction_sha256'] != selected['construction_sha256']
            or compatibility['runtime_manifest_sha256'] != manifest['runtime_manifest_sha256']):
        raise ValueError('Public compatibility is not bound to this exact candidate')
    scratch = ROOT / f'.runtime-work/c110919-owner104-rebind/saved-{condition}-{candidate}'
    if scratch.exists():
        raise ValueError('Use fresh saved attempt path: ' + str(scratch))
    scratch.mkdir(parents=True)
    source = scratch / 'fixture'
    subprocess.run([sys.executable, str(ROOT / 'runtime.py'), 'fixture',
                    '--recipe', str(ROOT / entry['fixture_recipe']),
                    '--output', str(source)], check=True, stdout=subprocess.DEVNULL)
    attempt = scratch / 'attempt'
    output = scratch / 'processed'
    subprocess.run([sys.executable, str(ROOT / 'runtime.py'), 'materialize',
                    '--manifest', str(MANIFEST), '--case', case_id,
                    '--candidate', candidate, '--output', str(attempt)],
                   check=True, stdout=subprocess.DEVNULL)
    for relative, expected in compatibility['fixture_manifest'].items():
        source_path = source / relative
        if not source_path.is_file() or (source_path.suffix != '.mkv' and sha(source_path) != expected):
            raise ValueError('Public source inventory changed: ' + relative)
        target = attempt / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source_path, target)
    before = {relative: sha(attempt / relative) for relative in compatibility['fixture_manifest']}
    command = [sys.executable, str(ROOT / 'runtime.py'), 'process-saved',
               '--manifest', str(MANIFEST), '--case', case_id,
               '--attempt', str(attempt),
               '--output', str(output), '--library', str(ROOT / 'runtime/library'),
               '--validator', str(VALIDATOR)]
    executed = subprocess.run(command, text=True, stdout=subprocess.PIPE,
                              stderr=subprocess.STDOUT, timeout=1800)
    log = folder / 'saved-command.log'
    log.write_text(executed.stdout)
    if executed.returncode:
        raise RuntimeError(f'Saved processing exit {executed.returncode}: {log}')
    processed = json.loads(executed.stdout)
    if (processed.get('passed') is not True or processed.get('recorded_only') is not True
            or processed.get('missing_evidence') or not processed.get('originals_preserved')
            or processed.get('candidate_id') != candidate
            or processed.get('native_revision', {}).get('construction_sha256') != selected['construction_sha256']):
        raise ValueError('Saved processing did not pass exact recorded-only replay')
    if any(sha(attempt / relative) != expected for relative, expected in before.items()):
        raise ValueError('Recorded-only replay changed an original source')
    proof = {'format': 'c110919-current-v2-candidate-saved-proof', 'passed': True,
             'case_id': case_id, 'candidate_id': candidate,
             'manifest_sha256': sha(MANIFEST),
             'construction_sha256': selected['construction_sha256'],
             'compatibility_sha256': sha(folder / 'compatibility.json'),
             'source_files': len(before), 'source_hashes_preserved': True,
             'video_bytes_regenerated_by_fixture': True,
             'processing_sha256': sha(log), 'processing': processed,
             'original_native_observed': False, 'physical_acceptance_claimed': False,
             'legal_verdict_claimed': False}
    target = folder / 'saved-proof.json'
    target.write_text(json.dumps(proof, indent=2, allow_nan=False) + '\n')
    print(json.dumps({'case': condition, 'candidate': candidate,
                      'source_files': len(before), 'proof_sha256': sha(target)}))


if __name__ == '__main__':
    os.environ.setdefault('SCENARIO_PIPELINE_OUTPUT_ROOT', str(ROOT / '.runtime-work/c110919-owner104'))
    run(sys.argv[1], sys.argv[2])
