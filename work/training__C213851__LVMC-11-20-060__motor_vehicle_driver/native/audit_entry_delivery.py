"""Independently audit saved roadway-return sources and camera decoding."""

import argparse
import hashlib
import json
from pathlib import Path

from measure_entry_return import measure_core_join
from measure_sidewalk import CAMERAS


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def audit(attempt, case_id):
    from worker_exchange.media import audit as audit_video

    attempt = Path(attempt)
    if not (attempt / 'original-entry-site-review.json').is_file():
        raise ValueError('Missing original roadway-entry site source')
    measured = measure_core_join(attempt, case_id)
    mapping = attempt / 'video_frames.jsonl'
    video = {}
    for camera in CAMERAS:
        path = attempt / (camera + '.mkv')
        decoded = audit_video(path, 1200, mapping_sha256=sha(mapping))
        if decoded.get('passed') is not True or decoded.get('frames') != 1200:
            raise ValueError('Roadway-entry source decode failed: ' + camera)
        video[camera] = {'sha256': sha(path),
                         'rgb_sequence_sha256': decoded['rgb_sequence_sha256'],
                         'dimensions': decoded['dimensions'],
                         'frames': decoded['frames']}
    return {'format': 'c213851-independent-entry-saved-source-audit',
            'case_id': case_id, 'source_kind': 'synthetic_diagnostic',
            'measured': measured, 'camera_decode': video,
            'frame_join_passed': True,
            'source_seal_sha256': measured['source_seal_sha256'],
            'original_pixels_semantically_reviewed': False,
            'physical_completion': None, 'legal_verdict': None,
            'delivery_accepted': False}


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--attempt', required=True)
    p.add_argument('--case', required=True)
    p.add_argument('--output', required=True)
    args = p.parse_args()
    output = Path(args.output)
    if output.exists():
        raise ValueError('Choose fresh audit output')
    result = audit(args.attempt, args.case)
    output.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'case_id': args.case,
                      'cameras': list(result['camera_decode']),
                      'frame_join_passed': True}))
