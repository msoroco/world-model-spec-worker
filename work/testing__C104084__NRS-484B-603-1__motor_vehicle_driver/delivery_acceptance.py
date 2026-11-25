"""Independent CPU acceptance of saved crest sources and a closed processing run.

Synthetic fixtures exercise the complete audit path. Physical and legal acceptance
remain for the later original Native delivery review.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from saved_crest_media import audit_media


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def accept(case: str, attempt: Path, processing: Path, physical: Path,
           *, omit_limit: bool = False) -> dict:
    source = attempt / 'capture' / 'crest-source'
    manifest_path = source / 'crest-manifest.json'
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    if manifest.get('case_id') != case:
        raise ValueError('selected saved source case differs')
    if omit_limit:
        manifest.pop('prescribed_limit_source', None)
    if not manifest.get('prescribed_limit_source'):
        raise ValueError('reviewed original prescribed limit source missing')
    source_proof = audit_media(source, manifest)
    if not all(source_proof['checks'][key] for key in
               ('native_source', 'all_participants', 'time_join',
                'full_video_decode', 'actual_pixels')):
        raise ValueError('saved source integrity check incomplete')
    if any(row['frame_count'] != 900 or not row['decoded_rgb24_sha256']
           for row in source_proof['camera_decodes'].values()):
        raise ValueError('actual four-view pixels incomplete')
    saved = json.loads(processing.read_text(encoding='utf-8'))
    if (saved.get('case_id') != case or saved.get('passed') is not True or
            saved.get('recorded_only') is not True or
            saved.get('originals_preserved') is not True or
            saved.get('timestamp_joins', {}).get('passed') is not True):
        raise ValueError('closed saved processing lacks original source checks')
    physical_proof = json.loads(physical.read_text(encoding='utf-8'))
    if physical_proof.get('case_id') != case:
        raise ValueError('physical outcome probe selects another case')
    expected = {'complete_motion': 'met', 'incomplete_motion': 'not_met',
                'missing_evidence': 'unverified'}
    observed = {}
    for fixture in physical_proof['fixtures']:
        kind = fixture['kind']
        path = physical.parent / fixture['result']
        if kind not in expected or _sha(path) != fixture['result_sha256']:
            raise ValueError('physical fixture changed')
        result = json.loads(path.read_text(encoding='utf-8'))
        observed[kind] = result['physical_checks']['maneuver']['status']
    if observed != expected:
        raise ValueError('three physical outcome states not distinguished')
    if physical_proof['lifecycle']['events'] != [
        'capture_finished', 'encoders_closed', 'restoration_verified',
        'native_exit', 'owner_released', 'saved_processing_started']:
        raise ValueError('Native ownership lifecycle incomplete')
    return {'case_id': case, 'source_manifest_sha256': _sha(manifest_path),
            'saved_receipt_sha256': _sha(processing),
            'physical_receipt_sha256': _sha(physical),
            'frame_count': source_proof['frame_count'],
            'checks': {**source_proof['checks'], 'physical_completion': True},
            'physical_outcome_probe': observed,
            'diagnostic_fixture': True,
            'physical_acceptance_claimed': False,
            'legal_acceptance_claimed': False}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('case')
    parser.add_argument('--attempt', type=Path, required=True)
    parser.add_argument('--processing', type=Path, required=True)
    parser.add_argument('--physical', type=Path, required=True)
    parser.add_argument('--omit-limit', action='store_true')
    args = parser.parse_args()
    print(json.dumps(accept(args.case, args.attempt, args.processing,
                            args.physical, omit_limit=args.omit_limit),
                     sort_keys=True))


if __name__ == '__main__':
    main()
