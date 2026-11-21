"""Run a finalized newly laid candidate through recorded-only saved processing."""
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
MANIFEST = HERE / 'draft-newly-laid-finalized-manifest.json'
sys.path.insert(0, str(ROOT / 'runtime/pipeline/scenario_pipeline'))
from worker_exchange.fixture_generator import inspect
from worker_exchange.runtime_cli import materialize


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def prove(short, candidate, compat, label):
    case = HERE.name + '__' + short
    manifest = json.loads(MANIFEST.read_text())
    entry = next(row for row in manifest['cases'] if row['case_id'] == case)
    selected = (entry if candidate == 'primary' else
                next(row for row in entry['candidates'] if row['id'] == candidate))
    compat = Path(compat).resolve()
    receipt = json.loads((compat / 'compatibility.json').read_text())
    if (receipt.get('passed') is not True or receipt.get('case_id') != case or
            receipt.get('candidate_id') != candidate or
            receipt.get('construction_sha256') != selected['construction_sha256']):
        raise ValueError('Finalized newly laid compatibility receipt differs')
    prefix = 'c183370-' + label + '-' + short + '-' + candidate
    source = ROOT / '.runtime-work' / (prefix + '-source')
    saved = ROOT / '.runtime-work' / (prefix + '-saved')
    log = HERE / (label + '-' + short + '-' + candidate + '-saved.log')
    out = HERE / (label + '-' + short + '-' + candidate + '-saved-proof.json')
    if any(path.exists() for path in (source, saved, log, out)):
        raise ValueError('Preserve previous newly laid saved proof')
    materialize(MANIFEST, case, source, candidate)
    recipe = json.loads((ROOT / entry['fixture_recipe']).read_text())
    spec = json.loads((ROOT / recipe['generator']['source']).read_text())
    for relative in inspect(spec):
        src, dst = compat / relative, source / relative
        if not src.is_file() or dst.exists():
            raise ValueError('Missing or shadowed diagnostic source: ' + relative)
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
    env = dict(os.environ)
    env['SCENARIO_PIPELINE_OUTPUT_ROOT'] = str(ROOT / '.runtime-work' /
                                              ('pipeline-output-' + label))
    command = [sys.executable, str(ROOT / 'runtime.py'), 'process-saved',
               '--manifest', str(MANIFEST), '--case', case,
               '--attempt', str(source), '--output', str(saved),
               '--library', str(ROOT / 'runtime/pipeline/library'),
               '--validator', str(ROOT / '.runtime-work/c10316-current-decoder/.lake/build/bin/adapterCheck')]
    with log.open('x') as stream:
        subprocess.run(command, cwd=ROOT, env=env, stdout=stream,
                       stderr=subprocess.STDOUT, check=True)
    processing = saved / 'v0001/processing.json'
    result = json.loads(processing.read_text())
    if (result.get('passed') is not True or
            result.get('recorded_only') is not True or
            result.get('originals_preserved') is not True or
            result.get('missing_evidence') is not False or
            result['timestamp_joins']['frames'] != 600 or
            result['analysis_revision']['construction_sha256'] != selected['construction_sha256'] or
            result.get('physical_acceptance_claimed') is not False):
        raise ValueError('Newly laid saved processing did not prove full diagnostic path')
    proof = {'case_id': case, 'candidate_id': candidate,
             'manifest_sha256': sha(MANIFEST),
             'construction_sha256': selected['construction_sha256'],
             'compatibility_sha256': sha(compat / 'compatibility.json'),
             'processing_sha256': sha(processing),
             'saved_log_sha256': sha(log),
             'synthetic_fixture': True, 'original_native_observed': False,
             'physical_or_legal_acceptance_claimed': False}
    out.write_text(json.dumps(proof, indent=2, sort_keys=True) + '\n')
    print(json.dumps({'case': short, 'candidate': candidate,
                      'proof_sha256': sha(out)}, sort_keys=True))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--case-suffix', required=True)
    parser.add_argument('--candidate', required=True)
    parser.add_argument('--compat-output', required=True)
    parser.add_argument('--label', default='update139')
    args = parser.parse_args()
    prove(args.case_suffix, args.candidate, args.compat_output, args.label)
