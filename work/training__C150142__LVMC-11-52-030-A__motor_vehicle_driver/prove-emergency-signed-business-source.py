"""Prove exact draft saved finalizer with source-shaped CPU rows and negatives."""
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
CASE = ROOT.name + '__emergency_vehicle_signed_business'
MANIFEST = ROOT / 'execution-manifest-diagnostic-emergency-signed-business-draft.json'
SPEC = importlib.util.spec_from_file_location('bus_source_helpers',
                                            ROOT / 'prove-tour-bus-saved-source.py')
SOURCE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(SOURCE)
sys.path.insert(0, str(REPO / 'runtime/pipeline/scenario_pipeline'))
from worker_exchange.runtime_cli import materialize


def source_rows(target, move=True):
    SOURCE.source_rows(target)
    (target / 'native-passenger-actors.jsonl').unlink()
    config = json.loads((target / 'config.json').read_text())
    approach = config['requested_approach_frames']
    with (target / 'native-service-worker-actors.jsonl').open('w') as output:
        for i in range(config['capture_frames']):
            since_stop = i - approach
            if not move or since_stop < 20:
                y = -10.0
            elif since_stop < 70:
                y = -10.0 + (since_stop - 20) * .05
            elif since_stop < 130:
                y = -7.5
            elif since_stop < 180:
                y = -7.5 - (since_stop - 130) * .05
            else:
                y = -10.0
            output.write(json.dumps({
                'frame': i, 'native_frame': i, 'time_s': i / 20,
                'source_kind': 'synthetic_native_sample', 'actor_id': 2,
                'blueprint': 'walker.pedestrian.0001',
                'center_native_xy_m': [config['requested_target_x_m'], y],
                'velocity_native_xyz_mps': [0, 0, 0]},
                allow_nan=False) + '\n')


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
                                     prefix='c150142-emergency-signed-business-source-') as temp:
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
           not observed['sign_present'] or \
           [row['name'] for row in observed['recorded_activity_events']] != [
               'business_activity'] or observed['necessary_business_established'] is not None or \
           observed['legal_verdict'] is not None:
            raise AssertionError('Emergency business source observation differs')
        missing_sign = parent / 'missing-sign'
        materialize(MANIFEST, CASE, missing_sign, candidate)
        source_rows(missing_sign)
        sign_map = json.loads((missing_sign / 'native-map-readback.json').read_text())
        sign_map['sign_readback']['present'] = False
        (missing_sign / 'native-map-readback.json').write_text(json.dumps(sign_map) + '\n')
        rejected_sign = run(missing_sign)
        if rejected_sign.returncode == 0 or \
           'Missing source-bound signed-curb readback' not in rejected_sign.stderr:
            raise AssertionError('Missing signed exception sign was accepted')
        missing = parent / 'missing-worker'
        materialize(MANIFEST, CASE, missing, candidate)
        for name in ('statutory-context.json', 'native-map-readback.json',
                     'native-raw-actors.jsonl'):
            (missing / name).write_text('')
        rejected = run(missing)
        if rejected.returncode == 0 or \
           'Missing required source: native-service-worker-actors.jsonl' not in rejected.stderr:
            raise AssertionError('Missing business worker source was accepted')
        static = parent / 'static-worker'
        materialize(MANIFEST, CASE, static, candidate)
        source_rows(static, move=False)
        rejected = run(static)
        if rejected.returncode == 0 or \
           'No measured service-worker approach' not in rejected.stderr:
            raise AssertionError('Static worker was accepted as business activity')
    return {'case_id': CASE, 'candidate_id': candidate,
            'source_kind': 'synthetic_native_sample', 'measured_stationary_duration_s': 12,
            'business_approach_dwell_departure_derived': True,
            'missing_worker_rejected': True, 'static_worker_rejected': True,
            'missing_sign_rejected': True, 'media_decoded': False, 'original_native_observed': False,
            'necessary_business_established': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--candidate', default='primary')
    args = parser.parse_args()
    print(json.dumps(prove(args.candidate), sort_keys=True))
