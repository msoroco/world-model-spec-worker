"""Seal original C109705 Native sources for recorded-only measurement.

This copies original OpenDRIVE bytes into the attempt and binds them to the
capture's original trace and camera index. It does not certify highway status,
physical completion, camera visibility or a legal departure judgment.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _pair(value, label):
    if not isinstance(value, list) or len(value) != 2 or any(
            type(x) not in (int, float) or not math.isfinite(x) for x in value):
        raise ValueError(f'{label} must be a finite xy point')
    return [float(x) for x in value]


def _binding(output, path):
    path = Path(path)
    if not path.is_file() or not path.resolve().is_relative_to(output.resolve()):
        raise ValueError('original Native source is missing or outside attempt')
    return {'path': str(path.relative_to(output)), 'sha256': _sha(path)}


def _reviewed_highway(survey_path, road):
    source = road.get('public_highway_source')
    if road.get('highway_review_status') != 'source_verified' or not isinstance(source, dict):
        raise ValueError('original public highway review is incomplete')
    name, digest = source.get('path'), source.get('sha256')
    if not isinstance(name, str) or not isinstance(digest, str):
        raise ValueError('original public highway review source binding missing')
    relative = Path(name)
    if relative.is_absolute() or not relative.parts or any(
            part in ('.', '..') for part in relative.parts):
        raise ValueError('original public highway review source path escapes survey')
    path = Path(survey_path).parent / relative
    if path.is_symlink() or not path.is_file() or _sha(path) != digest:
        raise ValueError('original public highway review source hash differs')
    review = json.loads(path.read_text(encoding='utf-8'))
    if (review.get('road_id') != road.get('road_id') or
            review.get('highway_status') != 'source_verified' or
            review.get('alley') is not False or
            not review.get('reviewer') or not review.get('source_citation')):
        raise ValueError('original public highway review conclusion missing')
    return source


def seal(output_dir, *, case_id, survey_path, survey_sha256, map_source_path,
         capture_receipt):
    output = Path(output_dir)
    if output.is_symlink() or not output.is_dir():
        raise ValueError('original Native attempt directory missing')
    raw = Path(survey_path).read_bytes()
    if hashlib.sha256(raw).hexdigest() != survey_sha256:
        raise ValueError('reviewed survey packet hash differs')
    survey = json.loads(raw)
    map_bytes = Path(map_source_path).read_bytes()
    if hashlib.sha256(map_bytes).hexdigest() != survey.get('source_sha256'):
        raise ValueError('original OpenDRIVE map source differs')
    if survey.get('cell_id') != 'C109705' or survey.get('maneuver') != 'left_turn':
        raise ValueError('reviewed survey cell or maneuver differs')
    roads = survey.get('intersecting_roads')
    if not isinstance(roads, list) or len(roads) != 2 or any(
            road.get('alley') is not False for road in roads):
        raise ValueError('original public highway review is incomplete')
    highway_sources = {str(road.get('road_id')): _reviewed_highway(survey_path, road)
                       for road in roads}
    ids = {road.get('road_id'): road for road in roads}
    approach, destination = survey.get('approach_road_id'), survey.get('destination_road_id')
    if set(ids) != {approach, destination}:
        raise ValueError('reviewed approach and destination road IDs differ')
    centerline = survey.get('destination_centerline_xy_m')
    if not isinstance(centerline, list) or len(centerline) != 2:
        raise ValueError('reviewed destination centerline missing')
    a, b = _pair(centerline[0], 'centerline start'), _pair(centerline[1], 'centerline end')
    delta = [b[0] - a[0], b[1] - a[1]]
    norm = math.hypot(*delta)
    if norm < 1:
        raise ValueError('reviewed destination centerline degenerate')
    kind = survey.get('destination_centerline_kind')
    if kind not in ('mapped', 'source_derived_imaginary'):
        raise ValueError('reviewed destination centerline kind missing')
    if kind == 'source_derived_imaginary' and not survey.get('imaginary_line_derivation_source'):
        raise ValueError('imaginary centerline derivation missing')
    if capture_receipt.get('case_id') != case_id or capture_receipt.get('frames') != 900:
        raise ValueError('original Native capture identity or duration differs')
    trace = Path(capture_receipt['trace_path'])
    camera = Path(capture_receipt['camera_index_path'])
    trace_binding, camera_binding = _binding(output, trace), _binding(output, camera)
    if trace_binding['sha256'] != capture_receipt.get('trace_sha256') or camera_binding[
            'sha256'] != capture_receipt.get('camera_index_sha256'):
        raise ValueError('original Native capture source hash differs')
    map_copy = output / 'original-map.xodr'
    map_packet_path = output / 'original-map-packet.json'
    manifest_path = output / 'source-manifest.json'
    bindings_path = output / 'original-bindings.json'
    for path in (map_copy, map_packet_path, manifest_path, bindings_path):
        if path.exists() or path.is_symlink():
            raise ValueError('refusing to overwrite sealed original Native source')
    with map_copy.open('xb') as stream:
        stream.write(map_bytes)
    map_packet = {
        'case_id': case_id, 'road_kind': 'two_directional_intersection',
        'approach_road_id': approach, 'destination_road_id': destination,
        'approach_two_directional': True, 'destination_two_directional': True,
        'approach_highway_status': 'source_verified',
        'destination_highway_status': 'source_verified',
        'source_path': map_copy.name, 'source_sha256': _sha(map_copy),
        'centerline_kind': kind, 'centerline_origin_xy_m': a,
        'destination_direction_xy': [x / norm for x in delta],
        'centerline_source': survey_sha256, 'direction_source': survey_sha256,
        'highway_sources': highway_sources,
    }
    with map_packet_path.open('x', encoding='utf-8') as stream:
        json.dump(map_packet, stream, indent=2, allow_nan=False)
        stream.write('\n')
    manifest = {
        'case_id': case_id, 'acquisition_kind': 'original_native',
        'rate_hz': 20, 'duration_s': 45,
        'camera_media_kind': 'original_png_frames',
        'survey_sha256': survey_sha256,
        'map': _binding(output, map_packet_path),
        'trace': trace_binding, 'camera_index': camera_binding,
        'physical_completion': False, 'statutory_judgment': None,
    }
    with manifest_path.open('x', encoding='utf-8') as stream:
        json.dump(manifest, stream, indent=2, allow_nan=False)
        stream.write('\n')
    with bindings_path.open('x', encoding='utf-8') as stream:
        json.dump(manifest, stream, indent=2, allow_nan=False)
        stream.write('\n')
    return {'source_manifest_path': str(manifest_path),
            'source_manifest_sha256': _sha(manifest_path),
            'original_map_sha256': _sha(map_copy),
            'physical_completion': False}
