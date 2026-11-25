"""Compare independently audited saved crest motion across exact cases."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from comparison_audit import compare
from saved_crest_audit import audit
from delivery_acceptance import accept


def _sha(data: object) -> str:
    return hashlib.sha256(json.dumps(data, sort_keys=True,
                                     separators=(',', ':')).encode()).hexdigest()


def _packet(source: Path) -> dict:
    manifest = json.loads((source / 'crest-manifest.json').read_text(encoding='utf-8'))
    proof = audit(source, manifest)
    frames = json.loads((source / manifest['motion_source']['path']).read_text(encoding='utf-8'))
    waypoints = json.loads((source / manifest['grade_source']['path']).read_text(encoding='utf-8'))
    return {
        'profile': manifest['profile'],
        'capture_id': manifest['native_capture_ref'],
        'waypoints': waypoints, 'frames': frames,
        'approach_start_m': manifest['approach_start_m'],
        'map_source_sha256': proof['source_sha256']['grade'],
        'ego_route_source_sha256': manifest['native_map_sha256'],
        'other_route_source_sha256': proof['source_sha256']['other_route'],
        'other_motion_source_sha256': _sha([(f['frame_id'], f['other_s_m'],
                                            f['other_actor_id']) for f in frames]),
        'highway_context_source_sha256': proof['source_sha256']['context'],
        'prescribed_limit_source_sha256': proof['source_sha256']['prescribed_limit'],
        'camera_contract_sha256': _sha(manifest['camera_dimensions']),
        'duration_s': manifest['duration_s'],
        'initial_speed_mps': proof['physical_measurements']['initial_speed_mps'],
        'source_manifest_sha256': hashlib.sha256(
            (source / 'crest-manifest.json').read_bytes()).hexdigest(),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('comparison_id')
    parser.add_argument('--left', type=Path, required=True)
    parser.add_argument('--right', type=Path, required=True)
    parser.add_argument('--left-processing', type=Path, required=True)
    parser.add_argument('--right-processing', type=Path, required=True)
    parser.add_argument('--left-review', type=Path, required=True)
    parser.add_argument('--right-review', type=Path, required=True)
    parser.add_argument('--diagnostic-test', action='store_true')
    parser.add_argument('--negative-context', action='store_true')
    args = parser.parse_args()
    pair = {'early_vs_late_precrest_decrease': ('early_decrease', 'late_decrease'),
            'decrease_vs_steady_approach': ('early_decrease', 'steady_approach')}
    if args.comparison_id not in pair:
        raise ValueError('unknown exact comparison')
    left_case, right_case = pair[args.comparison_id]
    assignment = 'testing__C104084__NRS-484B-603-1__motor_vehicle_driver'
    left_delivery = accept(f'{assignment}__{left_case}', args.left,
                           args.left_processing, args.left_review,
                           diagnostic_test=args.diagnostic_test)
    right_delivery = accept(f'{assignment}__{right_case}', args.right,
                            args.right_processing, args.right_review,
                            diagnostic_test=args.diagnostic_test)
    if not all(proof['checks'][key] for proof in (left_delivery, right_delivery)
               for key in ('native_source', 'all_participants', 'time_join',
                           'full_video_decode', 'actual_pixels',
                           'physical_completion', 'visibility_review')):
        raise ValueError('both original Native deliveries must pass full review')
    left = _packet(args.left / 'capture' / 'crest-source')
    right = _packet(args.right / 'capture' / 'crest-source')
    if args.negative_context:
        right['prescribed_limit_source_sha256'] = '0' * 64
    result = compare(left, right, expected_profiles=pair[args.comparison_id])
    print(json.dumps({'comparison_id': args.comparison_id,
                      'source_manifest_sha256': [left['source_manifest_sha256'],
                                                 right['source_manifest_sha256']],
                      'delivery_review_sha256': [left_delivery['review_receipt_sha256'],
                                                  right_delivery['review_receipt_sha256']],
                      'result': result,
                      'diagnostic_fixture': args.diagnostic_test,
                      'physical_acceptance_claimed': not args.diagnostic_test,
                      'legal_acceptance_claimed': False}, sort_keys=True))


if __name__ == '__main__':
    main()
