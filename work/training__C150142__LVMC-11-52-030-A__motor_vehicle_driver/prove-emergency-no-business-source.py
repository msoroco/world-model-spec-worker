"""Prove unsigned emergency no-worker saved finalizer and negative sources."""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
CASE = ROOT.name + '__emergency_vehicle_unsigned_no_business'
MANIFEST = ROOT / 'execution-manifest-diagnostic-emergency-no-business-draft.json'
SPEC = importlib.util.spec_from_file_location('bus_source_helpers',
                                            ROOT / 'prove-tour-bus-saved-source.py')
SOURCE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(SOURCE)
sys.path.insert(0, str(REPO / 'runtime/pipeline/scenario_pipeline'))
from worker_exchange.runtime_cli import materialize


def source_rows(target, inject_worker=False):
    SOURCE.source_rows(target, inject_walker_actor=inject_worker)
    (target / 'native-passenger-inventory.jsonl').rename(
        target / 'native-business-worker-inventory.jsonl')


def run(attempt):
    env = os.environ.copy()
    env['PYTHONPATH'] = str(REPO / 'runtime/pipeline/scenario_pipeline')
    return subprocess.run([sys.executable, str(attempt / 'finalize_selected.py'),
                           '--attempt', str(attempt),
                           '--output', str(attempt / 'analysis-report.json')],
                          cwd=attempt, env=env, text=True, capture_output=True)


def prove(candidate):
    if candidate not in ('primary', 'fallback1', 'fallback2', 'fallback3'):
        raise ValueError('Unknown emergency candidate')
    with tempfile.TemporaryDirectory(dir=REPO / '.runtime-work',
                                     prefix='c150142-emergency-business-source-') as temp:
        parent = Path(temp)
        positive = parent / 'positive'
        materialize(MANIFEST, CASE, positive, candidate)
        source_rows(positive)
        result = run(positive)
        if result.returncode:
            raise AssertionError('Saved finalizer failed: ' + result.stderr[-1800:])
        report = json.loads((positive / 'analysis-report.json').read_text())
        observed = report['measurements']['signed_curb_observation']['value']
        if observed['red_curb_stationary_duration_s'] != 12 or \
           observed['sign_present'] or \
           observed['recorded_activity_events'] != [] or \
           observed['necessary_business_established'] is not None or \
           observed['legal_verdict'] is not None:
            raise AssertionError('Emergency no-worker source observation differs')
        missing = parent / 'missing-inventory'
        materialize(MANIFEST, CASE, missing, candidate)
        for name in ('statutory-context.json', 'native-map-readback.json',
                     'native-raw-actors.jsonl'):
            (missing / name).write_text('')
        rejected = run(missing)
        if rejected.returncode == 0 or \
           'Missing required source: native-business-worker-inventory.jsonl' not in rejected.stderr:
            raise AssertionError('Missing business-worker inventory was accepted')
        unexpected = parent / 'unexpected-worker'
        materialize(MANIFEST, CASE, unexpected, candidate)
        source_rows(unexpected, inject_worker=True)
        rejected = run(unexpected)
        if rejected.returncode == 0 or \
           'No-worker case contains a pedestrian actor' not in rejected.stderr:
            raise AssertionError('Unexpected worker was accepted as absence')
    return {'case_id': CASE, 'candidate_id': candidate,
            'source_kind': 'synthetic_native_sample', 'measured_stationary_duration_s': 12,
            'no_worker_inventory_derived': True,
            'missing_inventory_rejected': True, 'unexpected_worker_rejected': True,
            'media_decoded': False, 'original_native_observed': False,
            'necessary_business_established': False,
            'actual_business_absence_established': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--candidate', default='primary')
    args = parser.parse_args()
    print(json.dumps(prove(args.candidate), sort_keys=True))
