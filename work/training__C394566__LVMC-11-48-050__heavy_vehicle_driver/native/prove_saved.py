"""Replay a fresh synthetic acquisition through saved-only processing.

This produces a diagnostic software proof. It cannot attest a real CARLA owner
release or original legal authority.
"""
import argparse
import json
import os
import shutil
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
PACKAGE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'runtime/scenario_pipeline'))
sys.path.insert(1, str(ROOT / 'runtime/python'))

from worker_exchange.common import sha, tree, digest, write
from worker_exchange.fixture_recipe import materialize as fixture
from worker_exchange.runtime_cli import materialize as construction
from worker_exchange.saved_processing import record_native_exit, run as saved


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True)
    parser.add_argument('--scratch', required=True)
    parser.add_argument('--library', required=True)
    parser.add_argument('--validator', required=True)
    args = parser.parse_args()
    output_root = Path(os.environ.get('SCENARIO_PIPELINE_OUTPUT_ROOT', '/')).resolve()
    if ROOT / '.runtime-work' not in output_root.parents:
        raise ValueError('Set the pipeline output root under .runtime-work')
    suffix = args.case.removeprefix(PACKAGE.name + '__')
    if not (PACKAGE / ('fixture-recipe-' + suffix + '.json')).is_file():
        raise ValueError('Selected case fixture recipe required')
    scratch = Path(args.scratch).resolve()
    if ROOT / '.runtime-work' not in scratch.parents or scratch.exists():
        raise ValueError('Fresh scratch under .runtime-work required')
    scratch.mkdir(parents=True)
    generated = scratch / 'fixture'
    attempt = scratch / 'attempt'
    report = scratch / 'saved'
    fixture(ROOT, PACKAGE / ('fixture-recipe-' + suffix + '.json'), generated)
    construction(PACKAGE / 'execution-probe-manifest.json', args.case, attempt, 'primary')
    original = tree(generated)
    for name in original:
        source, target = generated / name, attempt / name
        if target.exists():
            raise ValueError('Fixture shadows selected construction: ' + name)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
    seal_path = attempt / 'capture-seal.json'
    seal = json.loads(seal_path.read_text())
    seal.update(format='worker-sealed-capture', provenance_kind='synthetic_fixture',
                diagnostic_fixture=True, frames=600,
                restoration={'restored': True, 'scope': 'synthetic fixture, no CARLA world'},
                encoder_exit_codes={},
                sources={name: sha(attempt / name) for name in original if name != 'capture-seal.json'},
                native_revision={'construction_sha256': sha(attempt / 'construction.json'),
                                 'runner_sha256': sha(attempt / 'runner.py')},
                events=['capture_finished', 'encoders_closed', 'restoration_verified'],
                physical_acceptance_claimed=False)
    seal['source_digest'] = digest(seal['sources'])
    write(seal_path, seal)
    record_native_exit(attempt)
    result = saved(PACKAGE / 'execution-probe-manifest.json', args.case, attempt, report,
                   args.library, args.validator)
    if not result['passed'] or result['missing_evidence'] or not result['originals_preserved']:
        raise ValueError('Saved diagnostic did not preserve complete original acquisition')
    print(json.dumps({'case_id': args.case, 'passed': True,
                      'version': result['version'],
                      'processing_sha256': sha(Path(result['version']) / 'processing.json'),
                      'originals_preserved': True, 'diagnostic_fixture': True}, sort_keys=True))


if __name__ == '__main__':
    main()
