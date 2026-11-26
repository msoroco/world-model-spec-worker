"""Reopen two saved diagnostic cases before a controlled comparison audit."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from comparison_audit import audit_pair
from independent_cpu_delivery import audit as audit_delivery
from saved_measurement import measure_saved
from permission_sweep_audit import audit as audit_permission_sweep


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def summary(attempt: Path, case_id: str):
    attempt = Path(attempt)
    audit_delivery(attempt, case_id)
    path = attempt / 'pedestrian-source.json'
    source = json.loads(path.read_text())
    site = json.loads((attempt / source['site_ref']['path']).read_text())
    events = json.loads((attempt / source['events_ref']['path']).read_text())
    measured = measure_saved(attempt, source['site_ref'], source['events_ref'],
                             case_id, len(events))
    config = json.loads((attempt / 'config.json').read_text())
    provenance = json.loads((attempt / 'acquisition-provenance.json').read_text())
    diagnostic = provenance.get('diagnostic_fixture') is True
    review_ref = source.get('permission_review_ref')
    if not diagnostic and not review_ref:
        raise ValueError('original cited-device permission review missing')
    focus = config.get('focus_provision_id')
    disposition = None
    if focus and not diagnostic:
        cited = audit_permission_sweep(attempt, case_id, source['site_ref'], review_ref,
                                       source['events_ref'], len(events), focus)
        disposition = cited['focus_applicability']
    refs = {ref['path']: ref['sha256'] for ref in site['original_sources']}
    if not all(name in refs for name in ('map.json', 'head.json', 'device.json')):
        raise ValueError('original intersection source set differs')
    return {'case_suffix': case_id.rsplit('__', 1)[-1],
            'diagnostic_fixture': diagnostic,
            'permission_review_sha256': review_ref['sha256'] if review_ref else None,
            'map_source_sha256': refs['map.json'],
            'vehicle_signal_source_sha256': refs['head.json'],
            'pedestrian_device_source_sha256': refs['device.json'],
            'highway_boundary_source_sha256': refs['map.json'],
            'pedestrian_route_source_sha256': refs['map.json'],
            'camera_profile_sha256': hashlib.sha256(json.dumps({
                'cameras': config['cameras'], 'fps': config['fps'],
                'frame_count': config['frame_count']}, sort_keys=True).encode()).hexdigest(),
            'duration_frames': len(events),
            'focus_provision_id': focus, 'entry_delay_s': config.get('entry_delay_s'),
            'review_disposition': disposition,
            'first_highway_entry_time_s': measured['first_highway_entry_time_s'],
            'sole_green_arrow_frames': measured['sole_green_arrow_frames'],
            'first_highway_entry': measured['first_highway_entry'],
            'separate_walk_indication_without_entry': measured['separate_walk_frame_count'] > 0,
            'source_sha256': {'pedestrian-source.json': sha(path),
                              'original_events.json': source['events_ref']['sha256']}}


def compare(comparison_id, left_attempt, left_case_id, right_attempt, right_case_id):
    left = summary(Path(left_attempt), left_case_id)
    right = summary(Path(right_attempt), right_case_id)
    require_fixed_device(left, right)
    require_fixed_review(left, right)
    result = audit_pair(comparison_id, left, right)
    return dict(result, fixed_pedestrian_device_sha256=left['pedestrian_device_source_sha256'],
                source_pairs=[left['source_sha256'], right['source_sha256']],
                diagnostic_fixture=left['diagnostic_fixture'], statutory_permission='unresolved',
                fixed_permission_review_sha256=left['permission_review_sha256'])


def require_fixed_device(left, right):
    """The comparison cannot switch the separate governing device."""
    source = left.get('pedestrian_device_source_sha256')
    if not source or source != right.get('pedestrian_device_source_sha256'):
        raise ValueError('fixed condition differs: pedestrian_device_source_sha256')


def require_fixed_review(left, right):
    """A production pair must retain one cited-device applicability review."""
    if left.get('diagnostic_fixture') != right.get('diagnostic_fixture'):
        raise ValueError('comparison mixes diagnostic and original attempts')
    if left.get('diagnostic_fixture') is not True:
        source = left.get('permission_review_sha256')
        if not source or source != right.get('permission_review_sha256'):
            raise ValueError('fixed condition differs: permission_review_sha256')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--comparison-id', required=True)
    parser.add_argument('--left-attempt', type=Path, required=True)
    parser.add_argument('--left-case-id', required=True)
    parser.add_argument('--right-attempt', type=Path, required=True)
    parser.add_argument('--right-case-id', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = compare(args.comparison_id, args.left_attempt, args.left_case_id,
                     args.right_attempt, args.right_case_id)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + '\n')
    print(json.dumps(result, sort_keys=True))


if __name__ == '__main__':
    main()
