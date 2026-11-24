"""Independent saved original-source, pixel and route-completion audit.

This command reads a sealed Native attempt after owner release. It never drives
CARLA or decides the legal question. Synthetic fixtures can test it, but cannot
establish that a parcel authority or recording is original.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from physical_completion import evaluate
from saved_delivery import audit as audit_sources
from saved_delivery import source_file


def audit(attempt: Path, bundle: dict, *, expected_frames: int = 900) -> dict:
    source = audit_sources(attempt, bundle, expected_frames=expected_frames)
    map_path = source_file(attempt, bundle['map'], 'map')
    trace_path = source_file(attempt, bundle['trace'], 'trace')
    completion = evaluate(json.loads(map_path.read_text()), json.loads(trace_path.read_text()), bundle['case_id'])
    if completion['status'] != 'met':
        raise ValueError('Original physical route completion required: ' + completion['status'])
    return {'format': 'property-original-delivery-audit-v1',
            'case_id': bundle['case_id'], 'frame_count': source['frame_count'],
            'original_source_audit': source, 'physical_completion': completion,
            'map_sha256': hashlib.sha256(map_path.read_bytes()).hexdigest(),
            'trace_sha256': hashlib.sha256(trace_path.read_bytes()).hexdigest(),
            'physical_acceptance_claimed': False, 'legal_judgment': None}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', type=Path, required=True)
    parser.add_argument('--bundle', type=Path, required=True)
    parser.add_argument('--case', required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--expected-frames', type=int, default=900)
    args = parser.parse_args()
    bundle = json.loads(args.bundle.read_text())
    if bundle.get('case_id') != args.case:
        raise ValueError('Exact original audit case differs')
    result = audit(args.attempt, bundle, expected_frames=args.expected_frames)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + '\n')
    print(json.dumps({'case_id': args.case, 'source_and_pixels': 'passed',
                      'route_completion': result['physical_completion']['status'],
                      'physical_acceptance_claimed': False}))


if __name__ == '__main__':
    main()
