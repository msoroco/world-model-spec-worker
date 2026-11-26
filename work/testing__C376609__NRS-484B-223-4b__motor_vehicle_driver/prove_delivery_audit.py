"""Test exact delivery handoff protocol with explicitly diagnostic CPU documents."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SCRATCH = ROOT / '.runtime-work/c376609-owner-nov26/delivery-protocol-v2'
SCRIPT = HERE / 'delivery_audit.py'
CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n')


def run():
    SCRATCH.mkdir(parents=True, exist_ok=True)
    cases = json.loads((HERE / 'case-plan.json').read_text())['cases']
    for case in cases:
        case_id = case['case_id']
        suffix = case_id.removeprefix(HERE.name + '__')
        root = SCRATCH / suffix
        root.mkdir(exist_ok=False)
        videos = {name: hashlib.sha256((case_id + name).encode()).hexdigest() for name in CAMERAS}
        capture = {'case_id': case_id, 'diagnostic_fixture': True,
                   'frame_count': 900, 'video_sha256': videos}
        write(root / 'diagnostic-capture-audit.json', capture)
        review = {'case_id': case_id, 'diagnostic_fixture': True,
                  'capture_sha256': sha(root / 'diagnostic-capture-audit.json'),
                  'views': {name: {'video_sha256': videos[name], 'vehicle_visible': True}
                            for name in CAMERAS}}
        positive = root / 'pixel-review.json'
        negative = root / 'pixel-review-missing-view.json'
        write(positive, review)
        write(negative, {**review, 'views': {name: value for name, value in review['views'].items() if name != 'approach'}})
        physical = HERE / 'proofs' / 'physical' / suffix / 'complete-result.json'
        if not physical.is_file():
            raise ValueError('physical protocol result missing')
        base = [sys.executable, str(SCRIPT), '--case', case_id, '--attempt', str(root),
                '--physical', str(physical), '--diagnostic-fixture', '--review']
        env = dict(os.environ, SCENARIO_PIPELINE_OUTPUT_ROOT=str(SCRATCH),
                   TMPDIR=str(SCRATCH), PYTHONDONTWRITEBYTECODE='1')
        good = subprocess.run(base + [str(positive)], cwd=ROOT, env=env,
                              text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        bad = subprocess.run(base + [str(negative)], cwd=ROOT, env=env,
                             text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        good_log = HERE / ('proof-delivery-positive-' + suffix + '.log')
        bad_log = HERE / ('proof-delivery-negative-' + suffix + '.log')
        good_log.write_text(good.stdout.rstrip() + '\n')
        bad_log.write_text(bad.stdout.rstrip() + '\n')
        expected = 'independent pixel review missing four views'
        if good.returncode or bad.returncode == 0 or expected not in bad.stdout:
            raise ValueError('delivery protocol proof failed: ' + suffix)
        receipt = {'case_id': case_id, 'sets': ['full-test'],
                   'checks': ['native_source', 'all_participants', 'time_join',
                              'full_video_decode', 'actual_pixels', 'physical_completion'],
                   'test_exit_code': 0, 'negative_exit_code': bad.returncode,
                   'negative_expected_error': expected,
                   'command': ' '.join(base + [str(positive)]),
                   'negative_command': ' '.join(base + [str(negative)]),
                   'script': SCRIPT.name, 'script_sha256': sha(SCRIPT),
                   'test_log': good_log.name, 'test_log_sha256': sha(good_log),
                   'negative_log': bad_log.name, 'negative_log_sha256': sha(bad_log),
                   'diagnostic_scope': 'CPU protocol only; original Native source and independent pixels remain required'}
        write(HERE / ('delivery-acceptance-' + suffix + '.json'), receipt)
    return len(cases)


if __name__ == '__main__':
    print('independent source-gated delivery protocols:', run())
