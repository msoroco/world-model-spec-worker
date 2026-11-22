"""Bind a reviewed zone record to original Native map samples.

The packet records a human source review. This module checks provenance and
geometry consistency; it does not decide whether a turn is legally safe.
"""
import hashlib
import json
import math
from pathlib import Path


def sha_bytes(value):
    return hashlib.sha256(value).hexdigest()


def validate(packet, source_bytes, zone):
    if packet.get('format') != 'worker-zone-review-source-v1':
        raise ValueError('zone review format missing')
    if not packet.get('reviewer') or not packet.get('review_method'):
        raise ValueError('independent zone source review missing')
    if not packet.get('authority_citation') or packet.get('authority_source_sha256') != sha_bytes(source_bytes):
        raise ValueError('authority designation source missing or changed')
    if packet.get('designation') != 'official_no_passing_zone':
        raise ValueError('official zone designation has not been reviewed')
    if packet.get('destination_kind') not in ('adjoining_highway', 'other_left_turn'):
        raise ValueError('left-turn destination classification missing')
    if (packet.get('destination_road_id') != zone.get('destination_road_id') or
            packet.get('destination_lane_id') != zone.get('destination_lane_id')):
        raise ValueError('reviewed left-turn destination differs from Native map')
    destination = zone.get('destination_xy_m')
    reviewed = packet.get('destination_xy_m')
    if (not isinstance(destination, list) or not isinstance(reviewed, list) or
            len(destination) != 2 or len(reviewed) != 2 or
            any(type(v) not in (int, float) or not math.isfinite(v)
                for v in (*destination, *reviewed)) or
            math.hypot(destination[0]-reviewed[0], destination[1]-reviewed[1]) > 1.25):
        raise ValueError('reviewed left-turn destination location differs from Native map')
    if packet.get('subsections_3_and_4_reviewed') is not True:
        raise ValueError('crossing exceptions have not been reviewed')
    if packet.get('road_id') != zone.get('approach_road_id') or packet.get('lane_id') != zone.get('approach_lane_id'):
        raise ValueError('reviewed zone belongs to a different road or lane')
    begin, end = packet.get('zone_x_limits_m', (None, None))
    if not all(type(v) in (int, float) and math.isfinite(v) for v in (begin, end)) or begin >= end:
        raise ValueError('reviewed zone endpoints missing')
    crossing = zone.get('crossing_x_m')
    if type(crossing) not in (int, float) or not begin <= crossing <= end:
        raise ValueError('turn crossing lies outside reviewed zone')
    samples = zone.get('approach_marking_samples')
    if not isinstance(samples, list) or len(samples) < 2:
        raise ValueError('original approach marking inventory missing')
    previous = None
    for sample in samples:
        x, mapped = sample.get('requested_x_m'), sample.get('mapped_x_m')
        if not all(type(v) in (int, float) and math.isfinite(v) for v in (x, mapped)):
            raise ValueError('nonfinite map marking sample')
        if previous is not None and not 0 < x - previous <= zone.get('sample_interval_max_m', 0) + 1e-6:
            raise ValueError('map marking sample spacing differs')
        if abs(mapped-x) > 1.25 or not begin <= x <= end:
            raise ValueError('sampled map marking lies outside reviewed zone')
        if sample.get('road_id') != packet['road_id'] or sample.get('lane_id') != packet['lane_id']:
            raise ValueError('sampled map marking changes reviewed lane')
        if 'solid' not in str(sample.get('marking_type', '')).lower():
            raise ValueError('sampled approach lacks solid zone striping')
        previous = x
    return {'zone_extent_verified': True, 'statutory_exceptions_verified': True,
            'destination_kind': packet['destination_kind'],
            'destination_road_id': packet['destination_road_id'],
            'destination_lane_id': packet['destination_lane_id'],
            'authority_source_sha256': sha_bytes(source_bytes),
            'review_packet_sha256': sha_bytes(json.dumps(packet, sort_keys=True).encode()),
            'legal_safety_or_impediment_decided': False}


def copy_review(packet_path, zone, attempt):
    packet = json.loads(Path(packet_path).read_text())
    source_path = Path(packet.get('authority_source_path', ''))
    if not source_path.is_file():
        raise ValueError('reviewed authority source file missing')
    source = source_path.read_bytes()
    facts = validate(packet, source, zone)
    destination = Path(attempt)
    (destination/'zone-review-source.json').write_text(json.dumps(packet, indent=2, sort_keys=True)+'\n')
    (destination/'zone-authority-source.txt').write_bytes(source)
    return facts
