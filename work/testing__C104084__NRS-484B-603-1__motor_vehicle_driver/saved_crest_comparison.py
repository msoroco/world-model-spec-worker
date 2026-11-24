"""Compare two separately audited original hill-crest attempts."""
from __future__ import annotations

import json
from pathlib import Path

from comparison_audit import compare
from saved_crest_audit import _json_source, _source, audit


CONTEXT = ('ego_route_source_sha256', 'other_route_source_sha256',
           'other_motion_source_sha256', 'highway_context_source_sha256',
           'prescribed_limit_source_sha256', 'camera_contract_sha256')


def compare_saved(left_attempt, left_manifest, right_attempt, right_manifest,
                  *, expected_profiles):
    """Bind the original source hashes before comparing measured differences."""
    left_audit = audit(left_attempt, left_manifest)
    right_audit = audit(right_attempt, right_manifest)
    packets = []
    for root, manifest, proof in ((left_attempt, left_manifest, left_audit),
                                  (right_attempt, right_manifest, right_audit)):
        fixed = manifest.get('fixed_sources')
        if not manifest.get('capture_id') or not isinstance(fixed, dict) or set(fixed) != set(CONTEXT):
            raise ValueError('complete original comparison context required')
        grade, grade_sha = _json_source(Path(root), manifest['grade_source'])
        motion, _ = _json_source(Path(root), manifest['motion_source'])
        if grade_sha != proof['source_sha256']['grade']:
            raise ValueError('original map binding changed during comparison')
        packet = {'profile': manifest['profile'], 'capture_id': manifest['capture_id'],
                  'waypoints': grade, 'frames': motion,
                  'approach_start_m': manifest['approach_start_m'],
                  'map_source_sha256': grade_sha,
                  'duration_s': manifest['duration_s'],
                  'initial_speed_mps': motion[0]['ego_speed_mps']}
        packet.update({key: _source(Path(root), fixed[key])[1] for key in CONTEXT})
        expected_bound = {
            'other_route_source_sha256': proof['source_sha256']['other_route'],
            'highway_context_source_sha256': proof['source_sha256']['context'],
            'prescribed_limit_source_sha256': proof['source_sha256']['context'],
        }
        for key, expected_sha in expected_bound.items():
            if packet[key] != expected_sha:
                raise ValueError('fixed comparison source differs from audited original context')
        packets.append(packet)
    result = compare(*packets, expected_profiles=expected_profiles)
    result['saved_source_sha256'] = [left_audit['source_sha256'], right_audit['source_sha256']]
    result['physical_completion_verified'] = False
    result['actual_pixels_verified'] = False
    return result


def main():
    import argparse
    parser = argparse.ArgumentParser(description='Compare two saved original crest attempts')
    parser.add_argument('--left-attempt', required=True)
    parser.add_argument('--left-manifest', required=True)
    parser.add_argument('--right-attempt', required=True)
    parser.add_argument('--right-manifest', required=True)
    parser.add_argument('--left-profile', required=True)
    parser.add_argument('--right-profile', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    left = json.loads(Path(args.left_manifest).read_text(encoding='utf-8'))
    right = json.loads(Path(args.right_manifest).read_text(encoding='utf-8'))
    result = compare_saved(args.left_attempt, left, args.right_attempt, right,
                           expected_profiles=(args.left_profile, args.right_profile))
    output = Path(args.output)
    if output.exists():
        raise ValueError('retain prior comparison; choose a fresh output')
    output.write_text(json.dumps(result, indent=2, allow_nan=False)+'\n', encoding='utf-8')


if __name__ == '__main__':
    main()
