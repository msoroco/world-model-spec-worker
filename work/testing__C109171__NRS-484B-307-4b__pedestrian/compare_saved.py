"""Reopen two saved diagnostic cases before a controlled comparison audit."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from comparison_audit import audit_pair
from independent_cpu_delivery import audit as audit_delivery
from saved_measurement import measure_saved


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
    refs = {ref['path']: ref['sha256'] for ref in site['original_sources']}
    if not all(name in refs for name in ('map.json', 'head.json', 'device.json')):
        raise ValueError('original intersection source set differs')
    return {'case_suffix': case_id.rsplit('__', 1)[-1],
            'map_source_sha256': refs['map.json'],
            'vehicle_signal_source_sha256': refs['head.json'],
            'highway_boundary_source_sha256': refs['map.json'],
            'pedestrian_route_source_sha256': refs['map.json'],
            'camera_profile_sha256': hashlib.sha256(json.dumps({
                'cameras': config['cameras'], 'fps': config['fps'],
                'frame_count': config['frame_count']}, sort_keys=True).encode()).hexdigest(),
            'duration_frames': len(events),
            'sole_green_arrow_frames': measured['sole_green_arrow_frames'],
            'first_highway_entry': measured['first_highway_entry'],
            'separate_walk_indication_without_entry': measured['separate_walk_frame_count'] > 0,
            'source_sha256': {'pedestrian-source.json': sha(path),
                              'original_events.json': source['events_ref']['sha256']}}


def compare(comparison_id, left_attempt, left_case_id, right_attempt, right_case_id):
    left = summary(Path(left_attempt), left_case_id)
    right = summary(Path(right_attempt), right_case_id)
    result = audit_pair(comparison_id, left, right)
    return dict(result, source_pairs=[left['source_sha256'], right['source_sha256']],
                diagnostic_fixture=True, statutory_permission='unresolved')


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
