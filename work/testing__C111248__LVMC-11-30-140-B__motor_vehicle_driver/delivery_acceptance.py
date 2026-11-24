"""CPU proof of independent original-media and physical-status audit paths.

Diagnostic fixtures exercise rejection logic but never certify original Native
pixels, physical completion, or statutory conduct.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from delivery_audit import audit as audit_original_media


def check(case_id: str, manifest_path: Path, result_path: Path,
          *, expected_frames: int = 900, dimensions: dict | None = None) -> dict:
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    result = json.loads(result_path.read_text(encoding='utf-8'))
    if manifest.get('case_id') != case_id or result.get('case_id') != case_id:
        raise ValueError('delivery case identity mismatch')
    media = audit_original_media(manifest_path, expected_frames=expected_frames,
                                 dimensions=dimensions)
    participants = result.get('participants')
    if not isinstance(participants, dict) or not participants.get('driver_actor_id') or not participants.get('person_actor_id'):
        raise ValueError('delivery all participants missing')
    physical = result.get('physical_checks', {}).get('maneuver', {})
    if physical.get('status') not in ('met', 'not_met', 'unverified'):
        raise ValueError('delivery physical completion status missing')
    if result.get('frame_count') != expected_frames or result.get('time_join_passed') is not True:
        raise ValueError('delivery time join missing')
    diagnostic = result.get('diagnostic_fixture') is True
    native_source = result.get('provenance_kind') == 'native' and not diagnostic
    physical_complete = physical['status'] == 'met' and native_source
    return {'format': 'worker-blind-person-delivery-audit', 'case_id': case_id,
            'passed_cpu_checks': True, 'checks_executed': ['native_source', 'all_participants',
            'time_join', 'full_video_decode', 'actual_pixels', 'physical_completion'],
            'original_media_audit': media, 'manifest_sha256': hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
            'result_sha256': hashlib.sha256(result_path.read_bytes()).hexdigest(),
            'native_source_confirmed': native_source, 'physical_completion_confirmed': physical_complete,
            'actual_native_pixels_confirmed': native_source and media['passed'],
            'physical_acceptance_claimed': False, 'legal_acceptance_claimed': False}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True)
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--result', type=Path, required=True)
    parser.add_argument('--expected-frames', type=int, default=900)
    parser.add_argument('--diagnostic-small-profile', action='store_true')
    args = parser.parse_args()
    dimensions = {name: (1, 1) for name in ('front', 'left', 'right', 'rear')} if args.diagnostic_small_profile else None
    print(json.dumps(check(args.case, args.manifest, args.result,
                           expected_frames=args.expected_frames, dimensions=dimensions), sort_keys=True))


if __name__ == '__main__':
    main()
