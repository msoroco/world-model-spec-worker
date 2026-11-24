"""Diagnostic current-runner Core proof on an exact ignored long source.

The source is a previously retained synthetic Native-shaped full acquisition.
This direct Core proof does not substitute for a public fixture recipe receipt.
"""

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys


WORK = Path(__file__).resolve().parent
REPO = WORK.parents[1]
sys.path.insert(0, str(REPO / 'runtime/scenario_pipeline'))
from worker_exchange.common import digest
from worker_exchange.fixture_recipe import fixture_fingerprint
from worker_exchange.measurement_contract import verify_report
from worker_exchange.package_compatibility import _process_fixture, materialize_case
from worker_exchange.runtime_cli import execution_env


MANIFEST = WORK / 'current-runtime-runner-reference-bound-manifest.json'
SOURCE = REPO / '.runtime-work/c150142-direct-long-compat-tour-bus-below-primary-current-v2/fixture'
CASE = WORK.name + '__tour_bus_below'
CONTRACT = WORK / 'selected-primary/tour_bus_below/selected-measurement-contracts/tour_bus_below.json'


def sha(path):
    value = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            value.update(block)
    return value.hexdigest()


def run(output, validator):
    output = Path(output).resolve()
    validator = Path(validator).resolve()
    if REPO / '.runtime-work' not in output.parents or output.exists():
        raise ValueError('Use a fresh ignored .runtime-work output directory')
    if not SOURCE.is_dir() or not validator.is_file():
        raise ValueError('Missing exact ignored long source or pinned validator')
    frames = sum(1 for _ in (SOURCE / 'video_frames.jsonl').open())
    if frames != 36120:
        raise ValueError('Long source is not the complete 36,120-frame acquisition')
    manifest = json.loads(MANIFEST.read_text())
    entry = next(item for item in manifest['cases'] if item['case_id'] == CASE)
    output.mkdir(parents=True)
    fingerprint = fixture_fingerprint(SOURCE)
    source = {'fixture_sha256': digest(fingerprint), 'fixture_manifest': fingerprint}
    positive = output / 'positive'
    receipt = _process_fixture(MANIFEST, CASE, SOURCE, positive,
                               REPO / 'runtime/library', validator, 'primary', source)
    if (receipt.get('passed') is not True or receipt.get('case_id') != CASE or
            receipt.get('construction_sha256') != entry['construction_sha256']):
        raise ValueError('Pinned current-runner positive Core path failed')
    contract = json.loads(CONTRACT.read_text())
    measurements = verify_report(contract,
                                 json.loads((positive / 'analysis-report.json').read_text()),
                                 SOURCE)
    negative = output / 'negative'
    materialize_case(MANIFEST, CASE, negative, SOURCE, 'primary')
    removed = contract['negative']['remove'][0]
    (negative / removed).unlink()
    failure = subprocess.run(
        [sys.executable, str(negative / 'finalize_selected.py'),
         '--attempt', str(negative), '--output', str(negative / 'analysis-report.json')],
        cwd=negative, env=execution_env(), stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT, text=True, timeout=300)
    expected = contract['negative']['error_contains']
    log = output / 'negative-analysis.log'
    log.write_text(failure.stdout)
    if failure.returncode == 0 or expected not in failure.stdout:
        raise ValueError('Current-runner missing-source negative did not reject ' + removed)
    return {
        'format': 'c150142-current-runner-direct-long-core-v1',
        'passed': True, 'case_id': CASE, 'candidate_id': 'primary',
        'frames': frames, 'source_fixture_sha256': source['fixture_sha256'],
        'draft_manifest_sha256': sha(MANIFEST),
        'construction_sha256': entry['construction_sha256'],
        'core_checks': receipt['checks'],
        'positive_analysis_sha256': receipt['analysis_sha256'],
        'measurement_keys': sorted(measurements),
        'negative_removed': removed, 'negative_error_contains': expected,
        'negative_log_sha256': sha(log),
        'scope': 'direct synthetic Core; public fixture recipe receipt still required',
        'delivery_ready': False,
        'original_native_observed': False,
        'physical_acceptance_claimed': False,
        'legal_acceptance_claimed': False,
    }


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', required=True)
    parser.add_argument('--validator', required=True)
    args = parser.parse_args()
    print(json.dumps(run(args.output, args.validator), sort_keys=True, indent=2))
