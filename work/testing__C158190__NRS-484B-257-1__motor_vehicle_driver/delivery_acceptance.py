"""Independent CPU delivery preflight; diagnostic inputs never become original proof."""

import argparse
import hashlib
import json
from pathlib import Path

from yield_view_measurement import ASSIGNMENT


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def audit(case_id, processing_path, diagnostic=False):
    if not case_id.startswith(ASSIGNMENT + '__'):
        raise ValueError('unknown exact yield delivery case')
    path = Path(processing_path)
    processing = json.loads(path.read_text())
    if processing.get('case_id') != case_id or processing.get('passed') is not True:
        raise ValueError('saved processing identity or result missing')
    if processing.get('recorded_only') is not True or processing.get('originals_preserved') is not True:
        raise ValueError('saved processing changed originals')
    fixture = 'fixture-provenance.json' in processing.get('original_source_hashes', {})
    if fixture and not diagnostic:
        raise ValueError('diagnostic attempt cannot be original delivery')
    joins = processing.get('timestamp_joins', {})
    video = processing.get('final_video_checks', {})
    frames = 9 if diagnostic else 900
    if (joins.get('passed') is not True or joins.get('frames') != frames or
            video.get('passed') is not True or video.get('frames') != frames or
            not video.get('rgb_sequence_sha256')):
        raise ValueError('all-frame timestamp, pixel or decode proof missing')
    if processing.get('physical_acceptance_claimed') is not False:
        raise ValueError('unreviewed physical acceptance claim')
    result = json.loads(Path(processing['result']).read_text())
    if result.get('case_id') != case_id:
        raise ValueError('final result case differs')
    if diagnostic:
        if not fixture:
            raise ValueError('diagnostic provenance differs')
    elif fixture:
        raise ValueError('diagnostic attempt cannot be original delivery')
    if not diagnostic:
        raise ValueError('independent reviewed original site and physical packet required')
    return {'case_id': case_id, 'source_kind': 'synthetic_diagnostic_fixture',
            'processing_sha256': sha(path), 'timestamp_frames': frames,
            'decoded_frames': video['frames'], 'physical_acceptance': 'unverified',
            'legal_acceptance': None}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('case_id')
    parser.add_argument('processing', type=Path)
    parser.add_argument('--diagnostic', action='store_true')
    args = parser.parse_args()
    print(json.dumps(audit(args.case_id, args.processing, args.diagnostic), sort_keys=True))


if __name__ == '__main__':
    main()
