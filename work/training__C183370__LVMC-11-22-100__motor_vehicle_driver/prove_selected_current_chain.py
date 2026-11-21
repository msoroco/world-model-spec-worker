"""Run an exact selected candidate through current CPU diagnostic processing."""
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
sys.path.insert(0, str(ROOT / 'runtime/pipeline/scenario_pipeline'))
from worker_exchange.fixture_generator import inspect
from worker_exchange.runtime_cli import materialize

from delivery_audit import audit

MANIFEST = HERE / 'execution-manifest.json'
LIBRARY = ROOT / 'runtime/pipeline/library'
VALIDATOR = ROOT / '.runtime-work/c10316-current-decoder/.lake/build/bin/adapterCheck'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def run(arguments, log, env):
    with log.open('w') as stream:
        subprocess.run([sys.executable, str(ROOT / 'runtime.py'), *arguments],
                       cwd=ROOT, env=env, stdout=stream,
                       stderr=subprocess.STDOUT, check=True)


def prove(short, candidate, label):
    manifest = json.loads(MANIFEST.read_text())
    case = HERE.name + '__' + short
    entry = next(row for row in manifest['cases'] if row['case_id'] == case)
    selected = entry if candidate == 'primary' else next(
        row for row in entry['candidates'] if row['id'] == candidate)
    base = ROOT / '.runtime-work' / ('c183370-' + label + '-' + short + '-' + candidate)
    offline, compat, source, saved = (Path(str(base) + suffix) for suffix in
                                      ('-offline', '-compat', '-source', '-saved'))
    logs = {name: HERE / (label + '-' + short + '-' + candidate + '-' + name + '.log')
            for name in ('offline', 'compat', 'stage', 'saved')}
    env = dict(os.environ)
    env['SCENARIO_PIPELINE_OUTPUT_ROOT'] = str(ROOT / '.runtime-work' / ('pipeline-output-' + label))
    common = ['--manifest', str(MANIFEST), '--case', case, '--candidate', candidate]
    run(['offline', *common, '--output', str(offline), '--python', sys.executable],
        logs['offline'], env)
    run(['compatibility', *common, '--output', str(compat),
         '--library', str(LIBRARY), '--validator', str(VALIDATOR)],
        logs['compat'], env)
    with logs['stage'].open('w') as stream:
        materialize(MANIFEST, case, source, candidate)
        recipe = json.loads((ROOT / entry['fixture_recipe']).read_text())
        spec = json.loads((ROOT / recipe['generator']['source']).read_text())
        paths = inspect(spec)
        for relative in paths:
            src, dst = compat / relative, source / relative
            if not src.is_file() or dst.exists():
                raise ValueError('Diagnostic source missing or shadows construction: ' + relative)
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
        print(json.dumps({'staged_source_files': len(paths),
                          'synthetic_fixture': True}), file=stream)
    run(['process-saved', '--manifest', str(MANIFEST), '--case', case,
         '--attempt', str(source), '--output', str(saved),
         '--library', str(LIBRARY), '--validator', str(VALIDATOR)],
        logs['saved'], env)
    processing = saved / 'v0001/processing.json'
    diagnostic = audit(MANIFEST, case, candidate, source, processing, True)
    assert diagnostic['accepted'] is False
    selected_sha = selected['construction_sha256']
    receipt = json.loads((compat / 'compatibility.json').read_text())
    processed = json.loads(processing.read_text())
    assert receipt['passed'] is True and processed['passed'] is True
    assert processed['recorded_only'] is True and processed['originals_preserved'] is True
    assert processed['timestamp_joins']['frames'] == 600
    assert receipt['construction_sha256'] == processed['analysis_revision']['construction_sha256'] == selected_sha
    assert json.loads((source / 'candidate-selection.json').read_text())['manifest_sha256'] == sha(MANIFEST)
    proof = {'case_id': case, 'candidate_id': candidate, 'manifest_sha256': sha(MANIFEST),
             'construction_sha256': selected_sha, 'offline_selection_sha256': sha(offline / 'candidate-selection.json'),
             'compatibility_sha256': sha(compat / 'compatibility.json'),
             'saved_sha256': sha(processing), 'diagnostic_delivery_accepted': False,
             'original_native_verified': False, 'synthetic_fixture': True,
             'logs': {name: sha(path) for name, path in logs.items()}}
    out = HERE / (label + '-' + short + '-' + candidate + '-proof.json')
    if out.exists():
        raise ValueError('Retain previous selected proof')
    out.write_text(json.dumps(proof, indent=2, sort_keys=True) + '\n')
    print(json.dumps({'case': short, 'candidate': candidate,
                      'manifest_sha256': sha(MANIFEST), 'proof_sha256': sha(out)},
                     sort_keys=True))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--case-suffix', required=True)
    parser.add_argument('--candidate', default='primary')
    parser.add_argument('--label', default='update134')
    args = parser.parse_args()
    prove(args.case_suffix, args.candidate, args.label)
