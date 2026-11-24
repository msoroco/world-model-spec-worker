"""Finalize one sealed full-length intersection attempt with its saved media.

CPU checks prove source joins and decoding only. They do not establish a legal
exception, visible intersection contact, or physical completion in CARLA.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from finalize_observables import finalize
from intersection_observables import SourceError, _require
from native_media import audit_saved_acquisition
from native_scene import CASE_VARIANTS


ASSIGNMENT = 'testing__C110969__NRS-484B-450-1c__motor_vehicle_driver'


def finalize_saved(attempt: Path, *, expected_case: str) -> dict:
    attempt = Path(attempt)
    variant = expected_case.removeprefix(ASSIGNMENT + '__')
    _require(expected_case == ASSIGNMENT + '__' + variant and variant in CASE_VARIANTS,
             'unknown exact intersection case')
    manifest_path = attempt / 'source-manifest.json'
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    _require(manifest.get('case_id') == expected_case and manifest.get('native_run_id'),
             'saved exact case or Native run identity differs')
    observed = finalize(manifest_path)
    media = audit_saved_acquisition(attempt)
    frames = observed['frames']
    _require(len(frames) == 900 and media['frame_count'] == 900 and
             media['decoded_camera_frames'] == 3600,
             'complete 900-frame four-camera saved capture required')
    _require(media['media_manifest_sha256'] == manifest['media']['sha256'],
             'saved media manifest seal differs')
    _require(observed['case_id'] == media['case_id'] == expected_case and
             media['native_run_id'] == manifest['native_run_id'],
             'saved packet and camera identity differs')
    return {
        'format': 'worker-intersection-saved-delivery-v1',
        'assignment_id': ASSIGNMENT,
        'case_id': expected_case,
        'native_run_id': manifest['native_run_id'],
        'source_manifest_sha256': hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
        'source_seals': observed['source_seals'],
        'media_manifest_sha256': media['media_manifest_sha256'],
        'frame_count': len(frames),
        'decoded_camera_frames': media['decoded_camera_frames'],
        'observations': observed,
        'physical_completion_verified': False,
        'legal_conclusion': None,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--case', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    result = finalize_saved(Path(args.attempt), expected_case=args.case)
    output = Path(args.output)
    if output.exists():
        raise SourceError('retain prior finalized output; choose a fresh path')
    output.write_text(json.dumps(result, indent=2, allow_nan=False) + '\n',
                      encoding='utf-8')


if __name__ == '__main__':
    main()
