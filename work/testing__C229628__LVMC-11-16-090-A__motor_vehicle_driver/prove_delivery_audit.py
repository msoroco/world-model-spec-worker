"""Prove independent delivery rejection on marked synthetic protocol records."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

from contest_aid import CASES
from package_spec import AID, CAMERA_NAMES

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SCRATCH = ROOT / '.runtime-work/c229628-delivery-v2'
SCRIPT = HERE / 'delivery_audit.py'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, obj):
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + '\n')


def run():
    SCRATCH.mkdir(parents=True, exist_ok=True)
    for case in CASES:
        suffix = case.name
        case_id = AID + '__' + suffix
        root = SCRATCH / suffix
        if root.exists():
            raise ValueError('retain prior delivery fixture')
        root.mkdir()
        bindings = {name + '.mkv': hashlib.sha256((case_id + name).encode()).hexdigest()
                    for name in CAMERA_NAMES}
        capture = {'case_id': case_id, 'frame_count': 900, 'full_decode': True,
                   'receipt_sha256': hashlib.sha256(case_id.encode()).hexdigest(),
                   'source_bindings': bindings}
        write(root / 'diagnostic-capture-audit.json', capture)
        views = {name: {'video_sha256': bindings[name + '.mkv'],
                        'reviewer': 'CPU protocol fixture',
                        'samples': [{'frame': 100, 'ego_visible': True,
                                     'other_visible': True,
                                     'cue_visible': bool(case.cue and name == 'approach'),
                                     'decoded_rgb_sha256': hashlib.sha256((name + case_id).encode()).hexdigest()}]}
                 for name in CAMERA_NAMES}
        review = {'case_id': case_id,
                  'capture_receipt_sha256': capture['receipt_sha256'],
                  'views': views, 'legal_contest_interpretation': None,
                  'legal_aid_abet_interpretation': None}
        good = root / 'pixel-review.json'
        bad = root / 'pixel-review-missing-view.json'
        write(good, review)
        write(bad, dict(review, views={name: item for name, item in views.items()
                                       if name != 'approach'}))
        physical = HERE / 'proofs/physical' / suffix / 'complete_motion-result.json'
        if not physical.is_file():
            raise ValueError('physical CPU result missing: ' + suffix)
        base = [sys.executable, str(SCRIPT), '--case', case_id,
                '--attempt', str(root), '--physical', str(physical),
                '--diagnostic-fixture', '--review']
        env = dict(os.environ, SCENARIO_PIPELINE_OUTPUT_ROOT=str(SCRATCH),
                   TMPDIR=str(SCRATCH), PYTHONDONTWRITEBYTECODE='1')
        positive = subprocess.run(base + [str(good)], cwd=ROOT, env=env,
                                  text=True, capture_output=True)
        negative = subprocess.run(base + [str(bad)], cwd=ROOT, env=env,
                                  text=True, capture_output=True)
        good_log = HERE / ('proof-delivery-positive-' + suffix + '.log')
        bad_log = HERE / ('proof-delivery-negative-' + suffix + '.log')
        good_log.write_text((positive.stdout + positive.stderr).rstrip() + '\n')
        bad_log.write_text((negative.stdout + negative.stderr).rstrip() + '\n')
        error = 'independent four-view review missing'
        if positive.returncode or negative.returncode == 0 or error not in bad_log.read_text():
            raise ValueError('independent delivery protocol proof failed: ' + suffix)
        receipt = {'case_id': case_id, 'sets': ['full-test'],
                   'checks': ['native_source', 'all_participants', 'time_join',
                              'full_video_decode', 'actual_pixels', 'physical_completion'],
                   'test_exit_code': 0, 'negative_exit_code': negative.returncode,
                   'negative_expected_error': error,
                   'command': ' '.join(base + [str(good)]),
                   'negative_command': ' '.join(base + [str(bad)]),
                   'script': SCRIPT.name, 'script_sha256': sha(SCRIPT),
                   'test_log': good_log.name, 'test_log_sha256': sha(good_log),
                   'negative_log': bad_log.name, 'negative_log_sha256': sha(bad_log),
                   'diagnostic_scope': 'CPU protocol only; original Native evidence and human pixel review required'}
        write(HERE / ('delivery-acceptance-' + suffix + '.json'), receipt)
    return len(CASES)


if __name__ == '__main__':
    print('independent delivery CPU proofs:', run())
