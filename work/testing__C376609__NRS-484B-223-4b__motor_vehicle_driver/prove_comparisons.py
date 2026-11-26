"""Prove all eight exact comparison contracts with diagnostic protocol records."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SCRATCH = ROOT / '.runtime-work/c376609-owner-nov26/comparison-protocol-v1'
SCRIPT = HERE / 'comparison_audit.py'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def records(spec):
    rows = {}
    for index, case in enumerate(spec['case_ids']):
        rows[case] = {'format': 'worker-independent-original-delivery-measurement',
                      'case_id': case, 'frame_count': 900, 'full_video_decode': True,
                      'diagnostic_fixture': True, 'source_verified': False,
                      'public_highway_source_sha256': 'diagnostic-public-way',
                      'driver_actor_id': 'diagnostic-driver', 'vehicle_blueprint': 'diagnostic-vehicle',
                      'camera_plan_sha256': 'diagnostic-camera-plan', 'duration_frames': 900,
                      'map_sha256': 'diagnostic-map', 'result_sha256': 'diagnostic-result-' + str(index),
                      'observables': {name: index for name in spec['deliberate_differences']}}
    return rows


def run():
    SCRATCH.mkdir(parents=True, exist_ok=True)
    plan = json.loads((HERE / 'case-plan.json').read_text())
    receipts = []
    for spec in plan['comparisons']:
        cid = spec['comparison_id']
        path = SCRATCH / (cid + '-records.json')
        path.write_text(json.dumps(records(spec), indent=2) + '\n')
        base = [sys.executable, str(SCRIPT), '--comparison', cid, '--records', str(path)]
        env = dict(os.environ, SCENARIO_PIPELINE_OUTPUT_ROOT=str(SCRATCH),
                   TMPDIR=str(SCRATCH), PYTHONDONTWRITEBYTECODE='1')
        good = subprocess.run(base + ['--diagnostic'], cwd=ROOT, env=env, text=True,
                              stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        bad = subprocess.run(base, cwd=ROOT, env=env, text=True,
                             stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        good_log = HERE / ('proof-comparison-positive-' + cid + '.log')
        bad_log = HERE / ('proof-comparison-negative-' + cid + '.log')
        good_log.write_text(good.stdout.rstrip() + '\n')
        bad_log.write_text(bad.stdout.rstrip() + '\n')
        if good.returncode or bad.returncode == 0 or 'diagnostic/original provenance differs' not in bad.stdout:
            raise ValueError('exact source-bound comparison proof failed: ' + cid)
        receipts.append({'comparison_id': cid, 'case_ids': spec['case_ids'],
                         'positive_log': good_log.name, 'positive_sha256': sha(good_log),
                         'negative_log': bad_log.name, 'negative_sha256': sha(bad_log),
                         'original_source_verified': False, 'legal_verdict': None})
    (HERE / 'comparison-proposal.json').write_text(json.dumps({
        'format': 'worker-exact-comparison-proposal', 'assignment_id': HERE.name,
        'comparisons': receipts}, indent=2) + '\n')
    return len(receipts)


if __name__ == '__main__':
    print('exact comparison CPU protocol proofs:', run())
