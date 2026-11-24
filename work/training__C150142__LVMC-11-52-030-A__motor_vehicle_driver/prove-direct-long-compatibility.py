"""Exercise the pinned compatibility core on exact long ignored source media.

This worker diagnostic supplies large generated sources from an ignored saved
attempt. It cannot replace runtime.py compatibility's returned fixture recipe
receipt, whose pinned generator caps videos at 2,000 frames.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys


ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
sys.path.insert(0, str(REPO / 'runtime/scenario_pipeline'))
from worker_exchange.package_compatibility import _process_fixture, materialize_case
from worker_exchange.fixture_recipe import fixture_fingerprint
from worker_exchange.common import digest
from worker_exchange.measurement_contract import verify_report
from worker_exchange.runtime_cli import execution_env

VIEWS = ('overview', 'approach', 'reference_corner', 'driver_reference')
SOURCES = ('acquisition-provenance.json', 'native-map-readback.json',
           'native-passenger-actors.jsonl', 'native-raw-actors.jsonl',
           'road.xodr', 'statutory-context.json', 'trace.jsonl',
           'video_frames.jsonl') + tuple(view + '.mkv' for view in VIEWS)


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def run(case, candidate, attempt, root, validator):
    manifest = ROOT / 'execution-manifest.json'
    attempt = Path(attempt).resolve()
    root = Path(root).resolve()
    if REPO / '.runtime-work' not in attempt.parents or \
            REPO / '.runtime-work' not in root.parents:
        raise ValueError('Long diagnostic media and outputs must stay ignored')
    if root.exists():
        raise ValueError('Use a fresh direct-compatibility output root')
    case_id = ROOT.name + '__' + case
    selection = json.loads((attempt / 'candidate-selection.json').read_text())
    if selection['case_id'] != case_id or selection['candidate_id'] != candidate or \
            selection['manifest_sha256'] != sha(manifest):
        raise ValueError('Attempt selection differs from canonical manifest')
    frames = json.loads((attempt / 'config.json').read_text())['capture_frames']
    if frames not in (36120, 36121, 36122):
        raise ValueError('Expected exact long diagnostic frame count')
    root.mkdir(parents=True)
    fixture = root / 'fixture'
    fixture.mkdir()
    for name in SOURCES:
        source = attempt / name
        if not source.is_file():
            raise ValueError('Missing exact long source: ' + name)
        shutil.copy2(source, fixture / name)
    capture = attempt / 'capture'
    if not capture.is_dir():
        raise ValueError('Missing retained Native-shaped capture inventory')
    shutil.copytree(capture, fixture / 'capture')
    output = root / 'positive'
    fingerprint = fixture_fingerprint(fixture)
    source = {'fixture_sha256': digest(fingerprint), 'fixture_manifest': fingerprint}
    receipt = _process_fixture(manifest, case_id, fixture, output,
                               REPO / 'runtime/library', validator,
                               candidate, source)
    if receipt['passed'] is not True or receipt['case_id'] != case_id or \
            receipt['candidate_id'] != candidate:
        raise ValueError('Pinned compatibility core did not pass exact selection')
    contract = ROOT / 'selected-primary' / case / \
               'selected-measurement-contracts' / (case + '.json')
    contract_json = json.loads(contract.read_text())
    measurements = verify_report(contract_json,
                                 json.loads((output / 'analysis-report.json').read_text()),
                                 fixture)
    negative = root / 'negative'
    materialize_case(manifest, case_id, negative, fixture, candidate)
    removed = contract_json['negative']['remove'][0]
    (negative / removed).unlink()
    failure = subprocess.run(
        [sys.executable, str(negative / 'finalize_selected.py'),
         '--attempt', str(negative), '--output', str(negative / 'analysis-report.json')],
        cwd=negative, env=execution_env(), stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT, text=True, timeout=300)
    expected = contract_json['negative']['error_contains']
    negative_log = root / 'negative-analysis.log'
    negative_log.write_text(failure.stdout)
    if failure.returncode == 0 or expected not in failure.stdout:
        raise ValueError('Pinned negative case-source analysis did not reject ' + removed)
    return {'format': 'c150142-direct-long-compatibility-core-v1',
            'passed': True, 'case_id': case_id, 'candidate_id': candidate,
            'frames': frames, 'manifest_sha256': sha(manifest),
            'construction_sha256': selection['construction_sha256'],
            'core_checks': receipt['checks'],
            'positive_fixture_sha256': receipt['fixture_sha256'],
            'positive_analysis_sha256': receipt['analysis_sha256'],
            'measurement_keys': sorted(measurements),
            'negative_removed': removed,
            'negative_error_contains': expected,
            'negative_log_sha256': sha(negative_log),
            'scope': 'direct synthetic compatibility core; no pinned recipe receipt',
            'original_native_observed': False,
            'physical_acceptance_claimed': False,
            'legal_acceptance_claimed': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True)
    parser.add_argument('--candidate', default='primary')
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--validator', required=True)
    args = parser.parse_args()
    print(json.dumps(run(args.case, args.candidate, args.attempt,
                         args.output, Path(args.validator).resolve()), indent=2))
