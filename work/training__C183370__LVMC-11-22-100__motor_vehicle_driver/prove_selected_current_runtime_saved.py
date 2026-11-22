"""Run selected-manifest saved processing using audited diagnostic sources."""
import argparse
import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
MANIFEST = HERE / 'execution-manifest.json'
ASSETS = ROOT / '.runtime-work/c183370-selected-current-saved'
LIBRARY = ROOT / 'runtime/pipeline/library'
VALIDATOR = ROOT / '.runtime-work/c10316-current-decoder/.lake/build/bin/adapterCheck'
PYTHON = ROOT / '.venv-cpu/bin/python'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def command(args, log):
    env = dict(os.environ)
    env['SCENARIO_PIPELINE_OUTPUT_ROOT'] = str(ASSETS / 'output')
    with log.open('w') as stream:
        result = subprocess.run([str(PYTHON), str(ROOT / 'runtime.py'), *args],
                                cwd=ROOT, env=env, stdout=stream,
                                stderr=subprocess.STDOUT)
    if result.returncode:
        raise RuntimeError(f'Command failed ({result.returncode}); see {log}')


def prove(short, candidate):
    manifest = read(MANIFEST)
    case_id = HERE.name + '__' + short
    entry = next(e for e in manifest['cases'] if e['case_id'] == case_id)
    selected = entry if candidate == 'primary' else next(
        c for c in entry['candidates'] if c['id'] == candidate)
    source_compat = (ROOT / '.runtime-work/c183370-cutover-probe' /
                     ('compat' if candidate == 'primary' else 'compat-fallback1')
                     if short == 'reference' and candidate in ('primary', 'fallback1')
                     else ROOT / '.runtime-work/c183370-cutover-chains' /
                     short / candidate / 'compat')
    base = ASSETS / short / candidate
    returned = HERE / 'selected-current-runtime-saved-receipts' / short / candidate
    if base.exists() or returned.exists():
        raise ValueError('Preserve previous selected attempt')
    base.mkdir(parents=True)
    returned.mkdir(parents=True)
    source, saved = base / 'source', base / 'saved'
    command(['materialize', '--manifest', str(MANIFEST), '--case', case_id,
             '--candidate', candidate, '--output', str(source)],
            base / 'materialize.log')
    recipe = read(ROOT / entry['fixture_recipe'])
    spec = read(ROOT / recipe['generator']['source'])
    paths = (list(spec['files']) + [v['path'] for v in spec['videos']] +
             [g['path'] for g in spec['graphs']])
    for rel in paths:
        old, new = source_compat / rel, source / rel
        if not old.is_file():
            raise ValueError('Audited source missing: ' + rel)
        if new.exists():
            if sha(old) != sha(new):
                raise ValueError('Source conflicts with selected construction: ' + rel)
            continue
        new.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(old, new)
    command(['process-saved', '--manifest', str(MANIFEST), '--case', case_id,
             '--attempt', str(source), '--output', str(saved),
             '--library', str(LIBRARY), '--validator', str(VALIDATOR)],
            base / 'saved.log')
    selection = read(source / 'candidate-selection.json')
    processing = read(saved / 'v0001/processing.json')
    compatibility_path = HERE / selected['compatibility']['receipt']
    compatibility = read(compatibility_path)
    if not (selection['manifest_sha256'] == sha(MANIFEST) and
            selection['construction_sha256'] ==
            processing['analysis_revision']['construction_sha256'] ==
            compatibility['construction_sha256'] ==
            selected['construction_sha256'] and
            compatibility['runtime_manifest_sha256'] ==
            manifest['runtime_manifest_sha256'] and
            processing['passed'] and processing['recorded_only'] and
            processing['originals_preserved'] and
            not processing['missing_evidence'] and
            processing['timestamp_joins']['frames'] == 600):
        raise ValueError('Selected saved proof incomplete')
    dst = returned / 'processing.json'
    shutil.copyfile(saved / 'v0001/processing.json', dst)
    if dst.stat().st_size > 2 * 1024 * 1024:
        raise ValueError('Oversized returned processing receipt')
    proof = {'format': 'selected-current-runtime-saved-cpu-proof',
             'case_id': case_id, 'candidate_id': candidate,
             'selected_manifest_sha256': sha(MANIFEST),
             'runtime_manifest_sha256': manifest['runtime_manifest_sha256'],
             'construction_sha256': selected['construction_sha256'],
             'compatibility_receipt_sha256': sha(compatibility_path),
             'selection_sha256': sha(source / 'candidate-selection.json'),
             'processing_sha256': sha(dst), 'source_frames': 600,
             'recorded_only_saved_passed': True, 'synthetic_fixture': True,
             'original_native_verified': False,
             'physical_or_legal_acceptance_claimed': False}
    out = returned / 'proof.json'
    out.write_text(json.dumps(proof, indent=2, sort_keys=True) + '\n')
    print(json.dumps({'case': short, 'candidate': candidate,
                      'proof_sha256': sha(out)}), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True)
    parser.add_argument('--candidate', choices=(
        'primary', 'fallback1', 'fallback2', 'fallback3'), required=True)
    args = parser.parse_args()
    prove(args.case, args.candidate)
