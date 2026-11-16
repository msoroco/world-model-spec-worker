"""Independent CPU boundary proof for C10301 saved diagnostic sources.

This validates source integrity and physical-check provenance. A diagnostic
fixture can pass this software audit while its physical checks remain not_met.
"""

import argparse
import hashlib
import json
import io
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np
from PIL import Image

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / 'runtime/scenario_pipeline'))
sys.path.insert(0, str(HERE))

from diagnostic_comparison_audit import _check_trace_dynamics
from source_delivery_audit import CAMERAS, audit as audit_sources


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def audit_pixels(attempt, annotations):
    """Check source-bound, human-labelled subject and roadway pixels.

    This checks that labelled regions contain decodable visual detail. The labels
    and legal/physical visibility still require review of original Native video.
    """
    attempt = Path(attempt)
    if annotations.get('format') != 'worker-c10301-pixel-annotations':
        raise ValueError('Missing pixel annotation format')
    observations = annotations.get('observations')
    if not isinstance(observations, list) or not observations:
        raise ValueError('Missing subject and roadway pixel annotations')
    checked = []
    for item in observations:
        name = item.get('camera')
        frame = item.get('frame_index')
        if name not in CAMERAS or type(frame) is not int or frame < 0:
            raise ValueError('Invalid camera or frame annotation')
        video = attempt / name
        if not video.is_file() or item.get('source_sha256') != sha(video):
            raise ValueError('Pixel annotation source hash differs: ' + str(name))
        command = ['ffmpeg', '-v', 'error', '-i', str(video), '-vf',
                   f'select=eq(n\\,{frame})', '-frames:v', '1', '-f',
                   'image2pipe', '-vcodec', 'png', '-']
        decoded = subprocess.run(command, capture_output=True, check=False)
        if decoded.returncode or not decoded.stdout:
            raise ValueError('Annotated source frame could not be decoded')
        image = np.asarray(Image.open(io.BytesIO(decoded.stdout)).convert('RGB'))
        height, width = image.shape[:2]
        for role in ('subject', 'roadway'):
            box = item.get(role + '_box')
            if (not isinstance(box, list) or len(box) != 4 or
                    any(type(value) is not int for value in box)):
                raise ValueError('Missing ' + role + ' pixel box')
            x0, y0, x1, y1 = box
            if not (0 <= x0 < x1 <= width and 0 <= y0 < y1 <= height and
                    (x1 - x0) * (y1 - y0) >= 64):
                raise ValueError('Invalid ' + role + ' pixel box')
            pixels = image[y0:y1, x0:x1].astype(np.float32)
            if float(pixels.std(axis=(0, 1)).max()) < 4.0:
                raise ValueError('Annotated ' + role + ' pixels lack visual detail')
        checked.append({'camera': name, 'frame_index': frame,
                        'source_sha256': item['source_sha256']})
    return {'pixel_signal_checked': True, 'observations': checked,
            'semantic_visibility_confirmed': False,
            'human_review_required': True}


def audit(case_id, attempt, annotations=None):
    attempt = Path(attempt)
    result_path = attempt / 'result.json'
    if not result_path.is_file():
        raise ValueError('Missing sealed result')
    result = json.loads(result_path.read_text())
    if result.get('case_id') != case_id:
        raise ValueError('Saved result case identity differs')
    source = audit_sources(attempt, case_id)
    _check_trace_dynamics(attempt)
    checks = result.get('physical_checks')
    if not isinstance(checks, dict) or not {'setup', 'target', 'maneuver', 'attempt'} <= checks.keys():
        raise ValueError('Missing independent physical checks')
    for name, check in checks.items():
        if check.get('status') not in ('met', 'not_met', 'unverified'):
            raise ValueError('Invalid physical check status: ' + name)
        for ref, digest in check.get('sources', {}).items():
            path = attempt / ref
            if not path.is_file() or sha(path) != digest:
                raise ValueError('Physical completion source changed: ' + ref)
    if result.get('physical_acceptance_claimed') or result.get('legal_acceptance_claimed'):
        raise ValueError('Diagnostic asserted physical or legal acceptance')
    pixel_check = (audit_pixels(attempt, annotations) if annotations is not None else
                   {'pixel_signal_checked': False,
                    'semantic_visibility_confirmed': False,
                    'human_review_required': True,
                    'reason': 'Original-frame subject and roadway annotations absent'})
    return {'format': 'worker-c10301-delivery-diagnostic-audit',
            'case_id': case_id, 'software_source_integrity_passed': True,
            'source_frame_count': source['source_frame_count'],
            'sampled_peak_speed_mph': source['sampled_peak_speed_mph'],
            'physical_check_statuses': {name: check['status'] for name, check in checks.items()},
            'actual_pixels': pixel_check,
            'physical_acceptance_claimed': False, 'legal_acceptance_claimed': False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True)
    parser.add_argument('--mode', choices=('positive', 'negative'), required=True)
    parser.add_argument('--pixel-annotations')
    args = parser.parse_args()
    manifest = json.loads((HERE / 'execution-manifest.json').read_text())
    entry = next((row for row in manifest['cases'] if row['case_id'] == args.case), None)
    if entry is None:
        raise ValueError('Unknown selected case')
    receipt_path = HERE / entry['saved_processing']['receipt']
    if sha(receipt_path) != entry['saved_processing']['sha256']:
        raise ValueError('Saved processing receipt changed')
    receipt = json.loads(receipt_path.read_text())
    if (receipt.get('case_id') != args.case or not receipt.get('passed')
            or not receipt.get('recorded_only') or not receipt.get('originals_preserved')):
        raise ValueError('Saved processing boundary differs')
    attempt = Path(receipt['analysis_directory'])
    if sha(attempt / 'result.json') != receipt['result_sha256']:
        raise ValueError('Saved result hash changed')
    if args.mode == 'positive':
        annotations = (json.loads(Path(args.pixel_annotations).read_text())
                       if args.pixel_annotations else None)
        print(json.dumps(audit(args.case, attempt, annotations), sort_keys=True))
        return
    with tempfile.TemporaryDirectory(prefix='c10301-delivery-negative-') as temporary:
        altered = Path(temporary)
        for name in ('config.json', 'result.json', 'subject_motion.jsonl',
                     'video_frames.jsonl', 'trace.jsonl', 'road_context.json',
                     'capture/evidence.jsonl', *CAMERAS):
            path = altered / name
            path.parent.mkdir(parents=True, exist_ok=True)
            if name != 'overview.mkv':
                path.symlink_to(attempt / name)
        audit(args.case, altered)
    raise AssertionError('Missing source camera was accepted')


if __name__ == '__main__':
    main()
