"""Saved-only measured result for one exact paragraph-(a) right-pass case.

The source audit and full camera decode run before any result is written.
Diagnostic pixels establish software behavior only; no legal verdict is made.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from pass_right_audit import ASSIGNMENT, VARIANTS, audit_delivery


def finalize(attempt, manifest: dict, *, selected_case: str,
             diagnostic_profile=None) -> dict:
    if not isinstance(manifest, dict) or manifest.get('case_id') != selected_case:
        raise ValueError('selected exact right-pass case differs')
    variant = manifest.get('variant')
    if variant not in VARIANTS or selected_case != ASSIGNMENT + '__' + variant:
        raise ValueError('selected exact right-pass variant differs')
    audited = audit_delivery(Path(attempt), manifest,
                             diagnostic_profile=diagnostic_profile)
    measured = audited['measurement']
    if not measured['right_pass_observed'] or not measured['intersection_crossed_during_pass']:
        raise ValueError('original trace lacks exact intersection right pass')
    return {
        'format': 'worker-right-pass-saved-finalization',
        'assignment_id': ASSIGNMENT, 'case_id': selected_case,
        'observed_target_left_signal': measured['target_left_signal_during_pass'],
        'observed_target_left_turn': measured['target_left_motion_during_pass'],
        'right_pass_observed': measured['right_pass_observed'],
        'intersection_crossed_during_pass': measured['intersection_crossed_during_pass'],
        'frame_count': audited['frame_count'], 'fps': audited['fps'],
        'sources_sha256': {
            'map': audited['map_sha256'], 'trace': audited['trace_sha256'],
            'route_request': audited['route_request_sha256'],
            'live_map_binding': audited['live_map_binding_sha256'],
            'cameras': audited['camera_sha256']},
        'camera_pixel_sha256': audited['camera_pixel_sha256'],
        'production_camera_profile_verified': audited['production_camera_profile_verified'],
        'physical_visibility_confirmed': False,
        'physical_acceptance_claimed': False,
        'legal_outcome': 'unresolved',
    }


def main():
    parser = argparse.ArgumentParser(description='Finalize saved right-pass measurements')
    parser.add_argument('--attempt', type=Path, required=True)
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--case', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError('retain prior finalization; choose a fresh output')
    manifest = json.loads(args.manifest.read_text(encoding='utf-8'))
    result = finalize(args.attempt, manifest, selected_case=args.case)
    result['source_manifest_sha256'] = hashlib.sha256(args.manifest.read_bytes()).hexdigest()
    with args.output.open('x', encoding='utf-8') as stream:
        json.dump(result, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write('\n')


if __name__ == '__main__':
    main()
