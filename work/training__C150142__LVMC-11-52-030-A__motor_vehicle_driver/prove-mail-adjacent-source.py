"""Prove mail-adjacent saved finalizer with source-shaped CPU rows and negatives."""
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
CASE = ROOT.name + '__mail_adjacent_deposit'
MANIFEST = ROOT / 'execution-manifest-diagnostic-mail-adjacent-deposit-draft.json'
spec = importlib.util.spec_from_file_location('emergency_business_sources',
    ROOT / 'prove-emergency-business-source.py')
SOURCE = importlib.util.module_from_spec(spec)
spec.loader.exec_module(SOURCE)
sys.path.insert(0, str(REPO / 'runtime/pipeline/scenario_pipeline'))
from worker_exchange.runtime_cli import materialize


def source_rows(attempt, *, parcel_loss=True):
    SOURCE.source_rows(attempt)
    (attempt / 'native-service-worker-actors.jsonl').rename(
        attempt / 'native-mail-worker-actors.jsonl')
    workers = [json.loads(line) for line in
               (attempt / 'native-mail-worker-actors.jsonl').read_text().splitlines()]
    for worker in workers:
        worker['center_native_xy_m'][0] = 40
    (attempt / 'native-mail-worker-actors.jsonl').write_text(
        ''.join(json.dumps(worker, allow_nan=False) + '\n' for worker in workers))
    with (attempt / 'native-mail-parcel-inventory.jsonl').open('w') as stream:
        for worker in workers:
            frame = worker['frame']
            present = frame < 220 if parcel_loss else True
            stream.write(json.dumps({
                'frame': frame, 'native_frame': worker['native_frame'],
                'time_s': worker['time_s'], 'source_kind': worker['source_kind'],
                'present': present, 'actor_id': 3 if present else None,
                'blueprint': 'static.prop.box01' if present else None,
                'center_native_xy_m': worker['center_native_xy_m'] if present else None},
                allow_nan=False) + '\n')


def run(attempt):
    env = os.environ.copy()
    env['PYTHONPATH'] = str(REPO / 'runtime/pipeline/scenario_pipeline')
    return subprocess.run([sys.executable, str(attempt / 'finalize_selected.py'),
        '--attempt', str(attempt), '--output', str(attempt / 'analysis-report.json')],
        cwd=attempt, env=env, text=True, capture_output=True)


def prove(candidate):
    if candidate not in ('primary','fallback1','fallback2','fallback3'):
        raise ValueError('Unknown mail candidate')
    with tempfile.TemporaryDirectory(dir=REPO / '.runtime-work',
                                     prefix='c150142-mail-source-') as temp:
        base = Path(temp)
        positive = base / 'positive'
        materialize(MANIFEST, CASE, positive, candidate)
        source_rows(positive)
        passed = run(positive)
        if passed.returncode:
            raise AssertionError('Mail saved finalizer failed: ' + passed.stderr[-1600:])
        report = json.loads((positive / 'analysis-report.json').read_text())
        observed = report['measurements']['signed_curb_observation']['value']
        if observed['red_curb_stationary_duration_s'] != 12 or \
                not observed['mailbox_present'] or observed['sign_present'] or \
                [event['name'] for event in observed['recorded_activity_events']] != ['mail_deposit'] or \
                observed['expeditious_mail_deposit_established'] is not None or \
                observed['legal_verdict'] is not None:
            raise AssertionError('Mail source observation differs')
        missing_box = base / 'missing-box'
        materialize(MANIFEST, CASE, missing_box, candidate)
        source_rows(missing_box)
        readback = json.loads((missing_box / 'native-map-readback.json').read_text())
        readback['mailbox_readback']['present'] = False
        (missing_box / 'native-map-readback.json').write_text(json.dumps(readback) + '\n')
        rejected = run(missing_box)
        if rejected.returncode == 0 or 'Missing source-bound unsigned-curb readback' not in rejected.stderr:
            raise AssertionError('Missing mailbox readback was accepted')
        missing_parcel = base / 'missing-parcel'
        materialize(MANIFEST, CASE, missing_parcel, candidate)
        SOURCE.source_rows(missing_parcel)
        (missing_parcel / 'native-service-worker-actors.jsonl').rename(
            missing_parcel / 'native-mail-worker-actors.jsonl')
        rejected = run(missing_parcel)
        if rejected.returncode == 0 or \
                'Missing required source: native-mail-parcel-inventory.jsonl' not in rejected.stderr:
            raise AssertionError('Missing mail parcel inventory was accepted')
        no_loss = base / 'no-loss'
        materialize(MANIFEST, CASE, no_loss, candidate)
        source_rows(no_loss, parcel_loss=False)
        rejected = run(no_loss)
        if rejected.returncode == 0 or \
                'No single retained parcel disappearance' not in rejected.stderr:
            raise AssertionError('No parcel loss was accepted as deposit')
    return {'case_id': CASE, 'candidate_id': candidate,
        'source_kind':'synthetic_native_sample', 'stationary_duration_s':12,
        'mail_activity_proxy_derived':True,'missing_box_rejected':True,
        'missing_parcel_rejected':True,'no_loss_rejected':True,
        'actual_mail_deposit_established':False,'expeditiousness_established':False,
        'original_native_observed':False}


if __name__ == '__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--candidate',default='primary')
    args=parser.parse_args()
    print(json.dumps(prove(args.candidate),sort_keys=True))
