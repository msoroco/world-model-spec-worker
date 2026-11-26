"""Independently audit saved sidewalk sources and decoded camera coverage."""

import argparse
import hashlib
import json
from pathlib import Path

from measure_sidewalk import CAMERAS, measure_core_join


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def audit(attempt, case_id):
    from worker_exchange.media import audit as audit_video

    attempt = Path(attempt)
    if not (attempt / 'site-sources/sidewalk.json').is_file():
        raise ValueError('Missing original sidewalk source')
    measured = measure_core_join(attempt, case_id)
    mapping = attempt / 'video_frames.jsonl'
    video = {}
    for camera in CAMERAS:
        path = attempt / (camera + '.mkv')
        result = audit_video(path, 600, mapping_sha256=sha(mapping))
        if result.get('passed') is not True or result.get('frames') != 600:
            raise ValueError('Four-view source decode failed: ' + camera)
        video[camera] = {'sha256': sha(path),
                         'rgb_sequence_sha256': result['rgb_sequence_sha256'],
                         'dimensions': result['dimensions'],
                         'frames': result['frames']}
    return {
        'format': 'c213851-independent-saved-source-audit',
        'case_id': case_id,
        'source_kind': 'synthetic_diagnostic',
        'measured': measured,
        'camera_decode': video,
        'frame_join_passed': True,
        'source_seal_sha256': measured['source_seal_sha256'],
        'original_pixels_semantically_reviewed': False,
        'physical_completion': None,
        'legal_verdict': None,
        'delivery_accepted': False,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--case', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    result = audit(args.attempt, args.case)
    path = Path(args.output)
    if path.exists():
        raise ValueError('Choose a fresh audit output')
    path.write_text(json.dumps(result, indent=2, allow_nan=False) + '\n')
    print(json.dumps({'case_id': args.case, 'frame_join_passed': True,
                      'cameras': list(result['camera_decode'])}))


if __name__ == '__main__':
    main()
