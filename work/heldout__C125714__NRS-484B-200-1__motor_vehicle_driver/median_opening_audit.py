"""Independently bind an opening probe receipt to retained original roadway rows."""

import hashlib
import argparse
import json
from pathlib import Path

from median_opening_route import _inside, _validate_reference


def audit(attempt):
    attempt = Path(attempt)
    config = json.loads((attempt / 'config.json').read_text())
    receipt = json.loads((attempt / 'construction-probe.json').read_text())
    reference = config.get('median_opening_reference')
    polygon = _validate_reference(reference)
    expected_digest = hashlib.sha256(json.dumps(
        reference, sort_keys=True).encode()).hexdigest()
    if receipt.get('opening_reference_sha256') != expected_digest:
        raise ValueError('Opening reference changed after original capture')
    if receipt.get('case_id') != config.get('selected_case_id'):
        raise ValueError('Opening receipt case differs from original config')
    if (receipt.get('delivery_ready') is not False or
            receipt.get('physical_median_verified') is not False):
        raise ValueError('Opening construction receipt claims unsupported readiness')
    if (receipt.get('map_name') != reference['map_name'] or
            receipt.get('road_id') != reference['road_id'] or
            receipt.get('lane_id') != reference['lane_id']):
        raise ValueError('Opening receipt map/road/lane differs from source')
    rows = [json.loads(line) for line in (
        attempt / 'directed_roadway_footprints.jsonl').read_text().splitlines()
            if line.strip()]
    if len(rows) < 2:
        raise ValueError('Opening original roadway rows missing')
    frames = []
    observed = []
    for row in rows:
        frame = row['frame']
        if frames and frame != frames[-1] + 1:
            raise ValueError('Opening original roadway frames not continuous')
        if (row['subject_road_id'] != reference['road_id'] or
                row['subject_lane_id'] != reference['lane_id']):
            raise ValueError('Opening original roadway identity differs')
        frames.append(frame)
        if _inside(row['roadway_center_point_xy'], polygon):
            observed.append(frame)
    if frames != receipt.get('frames') or observed != receipt.get('observed_opening_frames'):
        raise ValueError('Opening receipt differs from original roadway frames')
    if not any(b == a + 1 for a, b in zip(observed, observed[1:])):
        raise ValueError('No consecutive original opening traversal frames')
    return {'case_id': receipt['case_id'],
            'opening_reference_sha256': expected_digest,
            'original_roadway_sha256': hashlib.sha256((
                attempt / 'directed_roadway_footprints.jsonl').read_bytes()).hexdigest(),
            'observed_opening_frames': observed,
            'physical_median_verified': False,
            'delivery_ready': False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    Path(args.output).write_text(json.dumps(audit(args.attempt), indent=2) + '\n')


if __name__ == '__main__':
    main()
