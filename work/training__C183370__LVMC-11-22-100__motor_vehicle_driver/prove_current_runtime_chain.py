"""Reprove one exact C183370 candidate with the pinned runtime.

Generated media and graph files stay in .runtime-work. Only bounded, hashed
receipts and the proof index are returned in work/.
"""
import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
MANIFEST = HERE / 'current-runtime-probe-manifest.json'
ASSETS = ROOT / '.runtime-work/c183370-cutover-chains'
LIBRARY = ROOT / 'runtime/pipeline/library'
VALIDATOR = ROOT / '.runtime-work/c10316-current-decoder/.lake/build/bin/adapterCheck'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def run(args, log):
    env = dict(os.environ)
    env['SCENARIO_PIPELINE_OUTPUT_ROOT'] = str(ROOT / '.runtime-work/c183370-cutover-chains/output')
    with log.open('w') as stream:
        result = subprocess.run([sys.executable, str(ROOT / 'runtime.py'), *args],
                                cwd=ROOT, env=env, stdout=stream,
                                stderr=subprocess.STDOUT)
    if result.returncode:
        raise RuntimeError(f'Command failed ({result.returncode}); see {log}')


def stage(source, target, spec):
    paths = list(spec['files']) + [v['path'] for v in spec['videos']] + [g['path'] for g in spec['graphs']]
    for rel in paths:
        old, new = source / rel, target / rel
        if not old.is_file():
            raise ValueError('Generated source missing: ' + rel)
        if new.exists():
            if sha(old) != sha(new):
                raise ValueError('Generated source conflicts with construction: ' + rel)
            continue
        new.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(old, new)
    return len(paths)


def prove(short, candidate):
    manifest = read(MANIFEST)
    cid = HERE.name + '__' + short
    case = next(c for c in manifest['cases'] if c['case_id'] == cid)
    selected = case if candidate == 'primary' else next(c for c in case['candidates'] if c['id'] == candidate)
    base = ASSETS / short / candidate
    if base.exists():
        raise ValueError('Attempt already exists; preserve it: ' + str(base))
    base.mkdir(parents=True)
    returned = HERE / 'cutover-receipts' / short / candidate
    if returned.exists():
        raise ValueError('Returned proof already exists: ' + str(returned))
    returned.mkdir(parents=True)
    common = ['--manifest', str(MANIFEST), '--case', cid, '--candidate', candidate]
    compat, source, saved = base / 'compat', base / 'source', base / 'saved'
    run(['compatibility', *common, '--output', str(compat),
         '--library', str(LIBRARY), '--validator', str(VALIDATOR)], base / 'compat-command.log')
    run(['materialize', *common, '--output', str(source)], base / 'materialize-command.log')
    recipe = read(ROOT / case['fixture_recipe'])
    spec = read(ROOT / recipe['generator']['source'])
    staged = stage(compat, source, spec)
    run(['process-saved', '--manifest', str(MANIFEST), '--case', cid,
         '--attempt', str(source), '--output', str(saved),
         '--library', str(LIBRARY), '--validator', str(VALIDATOR)], base / 'saved-command.log')
    selection = read(source / 'candidate-selection.json')
    compatibility = read(compat / 'compatibility.json')
    processing = read(saved / 'v0001/processing.json')
    if selection['manifest_sha256'] != sha(MANIFEST):
        raise ValueError('Stale exact manifest selection')
    if not (selection['construction_sha256'] == compatibility['construction_sha256'] ==
            processing['analysis_revision']['construction_sha256'] == selected['construction_sha256']):
        raise ValueError('Construction identity mismatch')
    if not (compatibility['passed'] and
            compatibility['negative_error_contains'] == 'Missing required source: live-readback.json' and
            processing['passed'] and processing['recorded_only'] and
            processing['originals_preserved'] and not processing['missing_evidence'] and
            processing['timestamp_joins']['frames'] == 600):
        raise ValueError('Required positive/negative/saved proof incomplete')
    source_files = {'compatibility.json': compat / 'compatibility.json',
                    'analysis.log': compat / 'compatibility-analysis.log',
                    'negative.log': compat / 'negative-analysis.log',
                    'processing.json': saved / 'v0001/processing.json'}
    hashes = {}
    for name, src in source_files.items():
        dst = returned / name
        shutil.copyfile(src, dst)
        if dst.stat().st_size > 2 * 1024 * 1024:
            raise ValueError('Oversized returned receipt: ' + name)
        hashes[name] = sha(dst)
    proof = {'format': 'current-runtime-exact-candidate-cpu-proof',
             'status': 'probe_only_selected_manifest_unchanged',
             'case_id': cid, 'candidate_id': candidate,
             'manifest_sha256': sha(MANIFEST),
             'runtime_manifest_sha256': manifest['runtime_manifest_sha256'],
             'construction_sha256': selected['construction_sha256'],
             'selection_sha256': sha(source / 'candidate-selection.json'),
             'staged_generated_sources': staged,
             'returned_receipts': hashes,
             'positive_compatibility_passed': True,
             'missing_source_negative_passed': True,
             'recorded_only_saved_passed': True,
             'source_frames': 600, 'synthetic_fixture': True,
             'original_native_verified': False,
             'physical_or_legal_acceptance_claimed': False}
    out = returned / 'proof.json'
    out.write_text(json.dumps(proof, indent=2, sort_keys=True) + '\n')
    print(json.dumps({'case': short, 'candidate': candidate, 'proof_sha256': sha(out)}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True)
    parser.add_argument('--candidate', choices=('primary', 'fallback1', 'fallback2', 'fallback3'), required=True)
    args = parser.parse_args()
    prove(args.case, args.candidate)
