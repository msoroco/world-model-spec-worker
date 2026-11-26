"""Prove the combined saved source, camera and review audit on CPU fixtures."""

import json
from pathlib import Path
import subprocess
import sys
import tempfile

from audit_saved_delivery import audit
from measure_original import CAMERAS, REVIEW_COPIES, sha
from prove_original import fixture
from review_original import OBSERVATIONS


ROOT = Path(__file__).resolve().parent


def reject(callback, fragment):
    try:
        callback()
    except ValueError as error:
        if fragment not in str(error):
            raise
    else:
        raise AssertionError('Damaged saved delivery accepted: ' + fragment)


def prove():
    scratch = Path('.runtime-work/c183370-saved-delivery').resolve()
    scratch.mkdir(parents=True, exist_ok=True)
    cases = []
    positives = 0
    negatives = 0
    with tempfile.TemporaryDirectory(dir=scratch) as directory:
        for suffix in ('probe_a', 'probe_b', 'probe_c', 'probe_d'):
            attempt = Path(directory) / suffix
            attempt.mkdir()
            case_id = fixture(attempt, suffix)
            config = json.loads((ROOT / suffix / 'config.json').read_text())
            for camera in CAMERAS:
                video = attempt / (camera + '.mkv')
                video.unlink()
                spec = config['cameras'][camera]
                command = ['ffmpeg', '-nostdin', '-v', 'error', '-f', 'lavfi',
                           '-i', 'color=c=blue:s=' + str(spec['width']) + 'x' +
                           str(spec['height']) + ':r=20:d=30',
                           '-frames:v', '600', '-c:v', 'ffv1', str(video)]
                subprocess.run(command, check=True, capture_output=True)
            seal_path = attempt / 'captured-source-hashes.json'
            seal = json.loads(seal_path.read_text())
            for camera in CAMERAS:
                name = camera + '.mkv'
                seal['sha256'][name] = sha(attempt / name)
            seal_path.write_text(json.dumps(seal) + '\n')
            config_path = attempt / 'fixture-config.json'
            config_path.write_text(json.dumps(config) + '\n')
            receipt = {
                'format': 'c183370-original-review-v1',
                'source_kind': 'synthetic_structural_review',
                'case_id': case_id,
                'reviewer': 'source-shaped CPU fixture',
                'source_seal_sha256': sha(seal_path),
                'frame_count': 600,
                'rate_hz': 20,
                'reviewed_sha256': {name: seal['sha256'][name] for name in
                    list(REVIEW_COPIES.values()) +
                    [camera + '.mkv' for camera in CAMERAS]},
                'observations': {name: {
                    'camera': 'flagger' if name.startswith('signal') or
                        name == 'flagger_identity' else 'overview',
                    'video_frame': 150 if name == 'signal_stop' else 350,
                    'observed': False,
                    'note': 'synthetic fixture; original pixels unreviewed',
                } for name in OBSERVATIONS},
            }
            receipt_path = attempt / 'review-receipt.json'
            receipt_path.write_text(json.dumps(receipt) + '\n')
            result = audit(attempt, config_path, receipt_path)
            if (not result['source_join_passed'] or
                    len(result['camera_decode']) != 4 or
                    result['measurement']['case_id'] != case_id or
                    result['statutory_location_basis'] !=
                        ('clearly_marked_construction_or_maintenance_area'
                         if suffix in ('probe_c', 'probe_d') else
                         'designated_temporary_zone') or
                    result['original_pixels_independently_verified'] or
                    result['physical_completion'] is not None or
                    result['legal_verdict'] is not None):
                raise AssertionError('Saved delivery audit result differs')
            cases.append(case_id)
            positives += 1
            output = attempt / 'saved-delivery-audit.json'
            command = [sys.executable, '-B', str(ROOT / 'audit_saved_delivery.py'),
                       '--attempt', str(attempt), '--config', str(config_path),
                       '--receipt', str(receipt_path), '--output', str(output)]
            subprocess.run(command, check=True, capture_output=True, text=True)
            if json.loads(output.read_text()) != result:
                raise AssertionError('Saved delivery CLI output differs')
            positives += 1
            video = attempt / 'flagger.mkv'
            original_video = video.read_bytes()
            video.write_bytes(original_video[:-50])
            reject(lambda: audit(attempt, config_path, receipt_path),
                   'source missing or changed')
            negatives += 1
            video.write_bytes(original_video)
            wrong = dict(receipt, reviewed_sha256={})
            receipt_path.write_text(json.dumps(wrong) + '\n')
            reject(lambda: audit(attempt, config_path, receipt_path),
                   'review source hashes differ')
            negatives += 1
            receipt_path.write_text(json.dumps(receipt) + '\n')
            config['duration_s'] = 29
            config_path.write_text(json.dumps(config) + '\n')
            reject(lambda: audit(attempt, config_path, receipt_path),
                   'case or duration differs')
            negatives += 1
            config['duration_s'] = 30
            config['cameras']['flagger']['width'] += 1
            config_path.write_text(json.dumps(config) + '\n')
            reject(lambda: audit(attempt, config_path, receipt_path),
                   'config differs from exact construction')
            negatives += 1
    return {
        'format': 'c183370-combined-saved-delivery-cpu-proof',
        'source_kind': 'synthetic_structural_fixture',
        'positive_count': positives,
        'negative_count': negatives,
        'cases': cases,
        'full_ffv1_decode': True,
        'original_pixels_reviewed': False,
        'physical_or_legal_outcome_claimed': False,
    }


if __name__ == '__main__':
    print(json.dumps(prove()))
