"""Source-shaped crosswalk occupancy measurement for NRS 484B.450(1)(e).

This measures original footprint overlap while stopped. It does not decide
whether the stop is necessary, directed, otherwise lawful, or a legal violation.
"""
import hashlib
import json
import math
from pathlib import Path

from shapely.geometry import Polygon

FRAMES = 600
RATE_HZ = 20
CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rows(path):
    return [json.loads(s) for s in Path(path).read_text().splitlines()]


def polygon(points):
    p = Polygon(points)
    if not p.is_valid or p.area <= 0:
        raise ValueError('Invalid source polygon')
    return p


def measure(root, case_id, source_kind='synthetic_cpu'):
    root = Path(root)
    if source_kind not in ('synthetic_cpu', 'original_native'):
        raise ValueError('Unsupported source kind')
    actors_file = root / 'actor-sources.jsonl'
    camera_file = root / 'camera-frames.jsonl'
    context_file = root / 'crosswalk-source.json'
    actors = rows(actors_file)
    camera = rows(camera_file)
    context = json.loads(context_file.read_text())
    if context.get('case_id') != case_id:
        raise ValueError('Crosswalk source case mismatch')
    if source_kind == 'original_native' and context.get('source_kind') != 'original_native':
        raise ValueError('Original Native crosswalk provenance missing')
    crosswalk = polygon(context['crosswalk_polygon_xy_m'])
    if context.get('crosswalk_source_kind') not in ('map_geometry', 'measured_marking'):
        raise ValueError('Crosswalk geometry source missing')
    if len(actors) != FRAMES or [r.get('frame') for r in actors] != list(range(FRAMES)):
        raise ValueError('Incomplete actor source frames')
    if len(camera) != FRAMES * 4:
        raise ValueError('Incomplete camera source frames')
    lookup = {(r.get('frame'), r.get('camera')): r for r in camera}
    if len(lookup) != len(camera):
        raise ValueError('Duplicate camera frame')
    for frame in range(FRAMES):
        for name in CAMERAS:
            item = lookup.get((frame, name))
            if item is None or len(item.get('rgb_sha256', '')) != 64:
                raise ValueError('Missing source camera RGB hash')
            if source_kind == 'original_native' and item.get('source_kind') != 'original_native':
                raise ValueError('Original Native camera provenance missing')
    occupied = []
    at_rest = []
    overlaps = []
    for frame, row in enumerate(actors):
        if row.get('case_id') != case_id or abs(float(row.get('time_s', -1)) - frame / RATE_HZ) > 1e-5:
            raise ValueError('Actor source identity/time mismatch')
        if source_kind == 'original_native' and row.get('source_kind') != 'original_native':
            raise ValueError('Original Native actor provenance missing')
        speed = float(row['ego_speed_mps'])
        if not math.isfinite(speed) or speed < 0:
            raise ValueError('Invalid original speed')
        footprint = polygon(row['ego_footprint_xy_m'])
        overlap = footprint.intersection(crosswalk).area
        overlaps.append(overlap)
        rest = speed <= .1
        at_rest.append(rest)
        occupied.append(rest and overlap > 1e-6)
        if row.get('forced_halt_source') not in (None, 'traffic_actor_trace'):
            raise ValueError('Unsupported forced-halt source')
        if row.get('direction_source') not in (None, 'officer_trace', 'device_trace'):
            raise ValueError('Unsupported direction source')
    result = {
        'format': 'c229397-crosswalk-source-measurement-v1',
        'case_id': case_id, 'source_kind': source_kind,
        'frames': FRAMES, 'rate_hz': RATE_HZ,
        'first_rest_frame': next((i for i, v in enumerate(at_rest) if v), None),
        'rest_frames': sum(at_rest),
        'crosswalk_occupied_while_at_rest_frames': sum(occupied),
        'first_occupied_rest_frame': next((i for i, v in enumerate(occupied) if v), None),
        'max_footprint_overlap_m2': max(overlaps),
        'crosswalk_source_kind': context['crosswalk_source_kind'],
        'source_sha256': {name: sha(root / name) for name in
                          ('actor-sources.jsonl', 'camera-frames.jsonl', 'crosswalk-source.json')},
        'exception_necessity': None,
        'exception_law_compliance': None,
        'exception_officer_or_device_direction': None,
        'legal_verdict': None,
        'overlap_epsilon_m2_is_law': False,
        'original_native_observed': source_kind == 'original_native',
        'delivery_ready': False,
    }
    return result
