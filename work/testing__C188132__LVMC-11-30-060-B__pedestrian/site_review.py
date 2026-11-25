"""Validate a separately reviewed source packet before Native overpass capture.

The packet records a local review decision and its source hashes. It is not a
substitute for later original Native pixels, motion, or legal acceptance.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def inspect(packet_path, map_path, scene, *, diagnostic=False):
    packet_path = Path(packet_path).resolve()
    map_path = Path(map_path).resolve()
    packet = json.loads(packet_path.read_text())
    if packet.get('format') != 'c188132-reviewed-overpass-site-v1':
        raise ValueError('reviewed original overpass site packet required')
    if packet.get('provenance_kind') != ('synthetic_fixture' if diagnostic else 'original_review'):
        raise ValueError('original reviewed site source required')
    if packet.get('case_id') != scene['case_id']:
        raise ValueError('reviewed site packet belongs to another case')
    if packet.get('map_sha256') != sha(map_path):
        raise ValueError('reviewed site map differs from Native source map')
    if packet.get('crossing_point_xy_m') != scene['crossing_point_xy_m']:
        raise ValueError('reviewed crossing point differs from construction')
    if packet.get('surface_road_id') != 1 or packet.get('deck_road_id') != 2:
        raise ValueError('reviewed surface/deck road identities differ')
    bounds = packet.get('roadway_y_bounds_m')
    if not isinstance(bounds, list) or len(bounds) != 2 or not (
            isinstance(bounds[0], (int, float)) and
            isinstance(bounds[1], (int, float)) and
            bounds[0] < -1.75 < bounds[1] and bounds[0] < 0 < bounds[1]):
        raise ValueError('reviewed roadway bounds do not include the crossing and vehicle')
    review = packet.get('independent_review')
    if not isinstance(review, dict) or not review.get('reviewer') or not review.get('source'):
        raise ValueError('independent reviewed site source required')
    if review['source'] != 'reviewed-site-source.txt':
        raise ValueError('reviewed site source must use its retained relative path')
    source = (packet_path.parent / review['source']).resolve()
    if not source.is_relative_to(packet_path.parent) or not source.is_file():
        raise ValueError('reviewed site source is missing')
    if review.get('sha256') != sha(source):
        raise ValueError('reviewed site source hash differs')
    if packet.get('provided_overhead_crossing') is not True or packet.get('usable_deck_access') is not True:
        raise ValueError('provided and accessible overhead crossing not established')
    designation = packet.get('municipal_designation')
    if not isinstance(designation, dict) or designation.get('prohibited') is not scene['designated_prohibition']:
        raise ValueError('reviewed municipal designation differs from exact case')
    if not designation.get('source') or not designation.get('sha256'):
        raise ValueError('municipal designation source required')
    if designation['source'] != 'municipal-designation-source.txt':
        raise ValueError('municipal designation source must use its retained relative path')
    municipal = (packet_path.parent / designation['source']).resolve()
    if not municipal.is_relative_to(packet_path.parent) or not municipal.is_file():
        raise ValueError('municipal designation source is missing')
    if designation['sha256'] != sha(municipal):
        raise ValueError('municipal designation source hash differs')
    return {'packet_sha256': sha(packet_path), 'site_source_sha256': sha(source),
            'municipal_source_sha256': sha(municipal),
            'roadway_y_bounds_m': bounds, 'designation_prohibited': designation['prohibited']}
