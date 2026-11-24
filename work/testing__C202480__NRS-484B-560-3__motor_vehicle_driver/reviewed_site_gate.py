"""Cross-check a proposed original crossing packet before Native dispatch.

This verifies source provenance and construction consistency, not the legal
meaning of a crossing instruction or the physical outcome of a recording.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from native_scene import inspect as inspect_scene
from site_source_review import inspect as inspect_lanes


def verify(packet_path: Path, plan_path: Path, case_id: str, *, diagnostic=False) -> dict:
    packet_path = Path(packet_path).resolve()
    packet, case, opendrive = inspect_scene(packet_path, plan_path, case_id)
    lanes = inspect_lanes(packet_path)
    if (lanes['case_id'] != case_id or
            lanes['marked_highway_lane_count'] != case['marked_highway_lane_count'] or
            lanes['opendrive_sha256'] != hashlib.sha256(opendrive).hexdigest()):
        raise ValueError('reviewed scene and original OpenDRIVE lane inventory differ')
    declared = {lane['opendrive_lane_id'] for lane in packet['marked_lanes']}
    observed = {lane['lane_id'] for lane in lanes['lanes']}
    if declared != observed:
        raise ValueError('marked lane identities differ from original OpenDRIVE')
    if not diagnostic:
        review = packet.get('source_review')
        if not isinstance(review, dict) or not all(
                isinstance(review.get(key), str) and review[key].strip()
                for key in ('reviewer', 'source', 'crossing_authority_basis',
                            'highway_boundary_basis', 'feasible_right_basis')):
            raise ValueError('independent original site source review missing')
        names = list(review.values()) + [camera.get('pose_source_citation', '')
                                         for camera in packet['cameras']]
        if any(any(term in value.lower() for term in ('synthetic', 'fixture', 'diagnostic'))
               for value in names):
            raise ValueError('diagnostic source cannot establish reviewed site')
    return {'format': 'c202480-original-site-preflight-v1',
            'case_id': case_id,
            'site_packet_sha256': hashlib.sha256(packet_path.read_bytes()).hexdigest(),
            'opendrive_sha256': lanes['opendrive_sha256'],
            'marked_highway_lane_count': lanes['marked_highway_lane_count'],
            'marked_lane_ids': sorted(observed),
            'diagnostic': diagnostic, 'physical_acceptance_claimed': False,
            'legal_judgment': 'unresolved'}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--site-packet', type=Path, required=True)
    parser.add_argument('--case-plan', type=Path, required=True)
    parser.add_argument('--case', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = verify(args.site_packet, args.case_plan, args.case)
    args.output.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'case_id': args.case, 'source_preflight_passed': True}))


if __name__ == '__main__':
    main()
