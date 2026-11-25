"""Audit an exact pair of retained original attempts before comparing them.

Both attempts must independently pass full source, four-camera pixel and
physical-route checks. This reports controlled observations, never a legal
judgment or a claim that an external authority is authentic.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from comparison_audit import audit_planned
from delivery_audit import audit as audit_delivery, audit_production
from saved_delivery import source_file


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def observed_packet(attempt: Path, bundle: dict, delivery: dict,
                    expected_frames: int) -> dict:
    map_path = source_file(attempt, bundle['map'], 'map')
    trace_path = source_file(attempt, bundle['trace'], 'trace')
    frame_path = source_file(attempt, bundle['frame_map'], 'frame map')
    map_packet = json.loads(map_path.read_text())
    trace = json.loads(trace_path.read_text())
    native = map_packet['native_map']
    road = source_file(attempt, native, 'original OpenDRIVE')
    statuses = delivery['original_source_audit']['observations']['traversed_property_statuses']
    if len(statuses) > 1:
        raise ValueError('multiple classified parcels traversed')
    parcel_class = statuses[0] if statuses else map_packet['properties'][0]['status']
    return {
        'case_id': bundle['case_id'], 'map_id': native['map_name'],
        'actor_id': trace['actor_class'],
        'capture_profile': 'four-original-cameras-20hz',
        'duration_frames': expected_frames,
        'approach_device_id': trace['approach_signal']['device_id'],
        'destination_device_id': trace['destination_signal']['device_id'],
        'parcel_class': parcel_class,
        'route_class': 'property' if statuses else 'roadway',
        'approach_state': trace['approach_signal']['state'],
        'destination_state': trace['destination_signal']['state'],
        'purpose': trace['purpose']['value'],
        'trace_sha256': _sha(trace_path),
        'map_source_sha256': _sha(road),
        'frame_map_sha256': _sha(frame_path),
    }


def audit_pair(comparison_id: str, left_attempt: Path, left_bundle: dict,
               right_attempt: Path, right_bundle: dict,
               *, expected_frames: int = 900, left_canonical: Path | None = None,
               right_canonical: Path | None = None,
               left_bundle_path: Path | None = None,
               right_bundle_path: Path | None = None,
               left_pixel_review: Path | None = None,
               right_pixel_review: Path | None = None) -> dict:
    if left_canonical is not None or right_canonical is not None:
        if not all((left_canonical, right_canonical, left_bundle_path,
                    right_bundle_path, left_pixel_review, right_pixel_review)):
            raise ValueError('both original video and pixel reviews required')
        left_delivery = audit_production(left_canonical, left_attempt, left_bundle_path,
                                         left_pixel_review, expected_frames=expected_frames)
        right_delivery = audit_production(right_canonical, right_attempt, right_bundle_path,
                                          right_pixel_review, expected_frames=expected_frames)
    else:
        left_delivery = audit_delivery(left_attempt, left_bundle, expected_frames=expected_frames)
        right_delivery = audit_delivery(right_attempt, right_bundle, expected_frames=expected_frames)
    left = observed_packet(left_attempt, left_bundle, left_delivery, expected_frames)
    right = observed_packet(right_attempt, right_bundle, right_delivery, expected_frames)
    result = audit_planned(left, right, comparison_id)
    return {'format': 'property-original-comparison-delivery-v1',
            'comparison_id': comparison_id, 'case_ids': result['case_ids'],
            'fixed_conditions_checked': result['fixed_conditions_checked'],
            'source_seals_checked': True,
            'deliberate_difference_observed': True,
            'left': left, 'right': right,
            'left_delivery': left_delivery, 'right_delivery': right_delivery,
            'physical_acceptance_claimed': False, 'legal_judgment': None}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--comparison', required=True)
    parser.add_argument('--left-attempt', type=Path, required=True)
    parser.add_argument('--left-bundle', type=Path, required=True)
    parser.add_argument('--right-attempt', type=Path, required=True)
    parser.add_argument('--right-bundle', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--expected-frames', type=int, default=900)
    parser.add_argument('--left-canonical', type=Path, required=True)
    parser.add_argument('--right-canonical', type=Path, required=True)
    parser.add_argument('--left-pixel-review', type=Path, required=True)
    parser.add_argument('--right-pixel-review', type=Path, required=True)
    args = parser.parse_args()
    result = audit_pair(args.comparison, args.left_attempt,
                        json.loads(args.left_bundle.read_text()), args.right_attempt,
                        json.loads(args.right_bundle.read_text()),
                        expected_frames=args.expected_frames,
                        left_canonical=args.left_canonical,
                        right_canonical=args.right_canonical,
                        left_bundle_path=args.left_bundle,
                        right_bundle_path=args.right_bundle,
                        left_pixel_review=args.left_pixel_review,
                        right_pixel_review=args.right_pixel_review)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + '\n')
    print(json.dumps({'comparison_id': args.comparison,
                      'original_attempts_audited': True,
                      'legal_judgment': None}, sort_keys=True))


if __name__ == '__main__':
    main()
