"""Replay one exact candidate through current recorded-only saved processing."""
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
SCRATCH = ROOT / '.runtime-work/c110919-8c-owner104'
VALIDATOR = ROOT / '.runtime-work/c110919-owner104/decoder/.lake/build/bin/adapterCheck'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def replay(suffix, candidate):
    if suffix not in ('probe_a', 'probe_b') or candidate not in ('primary', 'fallback1', 'fallback2'):
        raise ValueError('Unknown exact candidate')
    case_id = HERE.name + '__' + suffix
    manifest = json.loads(MANIFEST.read_text())
    entry = next(item for item in manifest['cases'] if item['case_id'] == case_id)
    selected = entry if candidate == 'primary' else next(item for item in entry['candidates'] if item['id'] == candidate)
    folder = HERE / 'current-v2-candidates' / suffix / candidate
    compatibility = json.loads((folder / 'compatibility.json').read_text())
    if (compatibility.get('passed') is not True or compatibility['candidate_id'] != candidate
            or compatibility['construction_sha256'] != selected['construction_sha256']
            or compatibility['runtime_manifest_sha256'] != manifest['runtime_manifest_sha256']):
        raise ValueError('Public receipt not bound to exact candidate')
    base = SCRATCH / f'saved-{suffix}-{candidate}'
    if base.exists():
        raise ValueError('Saved replay path already exists: ' + str(base))
    base.mkdir(parents=True)
    source = base / 'fixture'
    subprocess.run([sys.executable, str(ROOT / 'runtime.py'), 'fixture',
                    '--recipe', str(ROOT / entry['fixture_recipe']), '--output', str(source)],
                   check=True, stdout=subprocess.DEVNULL)
    attempt, output = base / 'attempt', base / 'processed'
    subprocess.run([sys.executable, str(ROOT / 'runtime.py'), 'materialize',
                    '--manifest', str(MANIFEST), '--case', case_id,
                    '--candidate', candidate, '--output', str(attempt)],
                   check=True, stdout=subprocess.DEVNULL)
    for relative, expected in compatibility['fixture_manifest'].items():
        original = source / relative
        if not original.is_file() or (original.suffix != '.mkv' and sha(original) != expected):
            raise ValueError('Public source inventory changed: ' + relative)
        target = attempt / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(original, target)
    original_hashes = {relative: sha(attempt / relative) for relative in compatibility['fixture_manifest']}
    command = [sys.executable, str(ROOT / 'runtime.py'), 'process-saved',
               '--manifest', str(MANIFEST), '--case', case_id, '--attempt', str(attempt),
               '--output', str(output), '--library', str(ROOT / 'runtime/library'),
               '--validator', str(VALIDATOR)]
    executed = subprocess.run(command, text=True, stdout=subprocess.PIPE,
                              stderr=subprocess.STDOUT, timeout=1800)
    log = folder / 'saved-command.log'
    log.write_text(executed.stdout)
    if executed.returncode:
        raise RuntimeError(f'Saved replay exit {executed.returncode}: {log}')
    processed = json.loads(executed.stdout)
    if (processed.get('passed') is not True or processed.get('recorded_only') is not True
            or processed.get('missing_evidence') or not processed.get('originals_preserved')
            or processed.get('candidate_id') != candidate
            or processed.get('native_revision', {}).get('construction_sha256') != selected['construction_sha256']):
        raise ValueError('Saved replay did not prove selected candidate')
    if any(sha(attempt / relative) != digest for relative, digest in original_hashes.items()):
        raise ValueError('Recorded-only replay mutated source')
    proof = {'format': 'c110919-8c-current-v2-saved-proof', 'passed': True,
             'case_id': case_id, 'candidate_id': candidate,
             'manifest_sha256': sha(MANIFEST), 'construction_sha256': selected['construction_sha256'],
             'compatibility_sha256': sha(folder / 'compatibility.json'),
             'source_files': len(original_hashes), 'source_hashes_preserved': True,
             'video_bytes_regenerated_by_fixture': True, 'processing_sha256': sha(log),
             'processing': processed, 'original_native_observed': False,
             'physical_acceptance_claimed': False, 'legal_verdict_claimed': False}
    target = folder / 'saved-proof.json'
    target.write_text(json.dumps(proof, indent=2, allow_nan=False) + '\n')
    print(json.dumps({'case': suffix, 'candidate': candidate,
                      'source_files': len(original_hashes), 'proof_sha256': sha(target)}), flush=True)


if __name__ == '__main__':
    os.environ.setdefault('SCENARIO_PIPELINE_OUTPUT_ROOT', str(SCRATCH))
    replay(sys.argv[1], sys.argv[2])
