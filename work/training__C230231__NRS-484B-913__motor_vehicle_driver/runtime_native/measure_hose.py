"""Measure driving over a sourced fire hose; never infer a legal verdict."""
import hashlib
import json
import math
from pathlib import Path

from shapely.geometry import LineString, Polygon

FRAMES = 600
CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read_rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines()]


def _polygon(points):
    result = Polygon(points)
    if not result.is_valid or result.area <= 0:
        raise ValueError('Invalid source vehicle footprint')
    return result


def measure(root, case_id, source_kind='synthetic_cpu'):
    root = Path(root)
    if source_kind not in ('synthetic_cpu', 'original_native'):
        raise ValueError('Unsupported source kind')
    actors_file = root / 'actor-sources.jsonl'
    cameras_file = root / 'camera-frames.jsonl'
    hose_file = root / 'hose-source.json'
    actors = read_rows(actors_file)
    cameras = read_rows(cameras_file)
    hose = json.loads(hose_file.read_text())
    if hose.get('case_id') != case_id:
        raise ValueError('Hose source case mismatch')
    if hose.get('way_kind') not in ('highway', 'private_way', 'private_place'):
        raise ValueError('Qualifying way source missing')
    if hose.get('purpose') not in ('fire', 'alarm', 'practice_run'):
        raise ValueError('Fire department use source missing')
    if hose.get('department_hose_source') not in ('asset_inventory', 'operator_readback'):
        raise ValueError('Fire department hose source missing')
    if hose.get('cover_inventory_source') not in ('asset_inventory', 'operator_readback'):
        raise ValueError('Hose protection inventory source missing')
    if not isinstance(hose.get('cover_or_ramp_present'), bool):
        raise ValueError('Hose protection state missing')
    hose_path = LineString(hose['hose_centerline_xy_m'])
    radius = float(hose['hose_radius_m'])
    if not hose_path.is_simple or hose_path.length <= 0 or not 0 < radius < 1:
        raise ValueError('Invalid source hose geometry')
    region = hose_path.buffer(radius)
    if len(actors) != FRAMES or [r.get('frame') for r in actors] != list(range(FRAMES)):
        raise ValueError('Incomplete actor source frames')
    if len(cameras) != FRAMES * len(CAMERAS):
        raise ValueError('Incomplete camera source frames')
    camera_by_frame = {(r.get('frame'), r.get('camera')): r for r in cameras}
    if len(camera_by_frame) != len(cameras):
        raise ValueError('Duplicate camera source frame')
    for frame in range(FRAMES):
        for name in CAMERAS:
            row = camera_by_frame.get((frame, name))
            if row is None or len(row.get('rgb_sha256', '')) != 64:
                raise ValueError('Missing source camera RGB hash')
    driven_overlap = []
    centers = []
    for frame, row in enumerate(actors):
        if row.get('case_id') != case_id or abs(float(row.get('time_s', -1)) - frame / 20) > 1e-5:
            raise ValueError('Actor source identity/time mismatch')
        speed = float(row['ego_speed_mps'])
        if not math.isfinite(speed) or speed < 0:
            raise ValueError('Invalid source speed')
        footprint = _polygon(row['ego_footprint_xy_m'])
        center = footprint.centroid
        centers.append((center.x, center.y))
        driven_overlap.append(speed > .1 and footprint.intersects(region))
    path_length = sum(math.dist(a, b) for a, b in zip(centers, centers[1:]))
    consent = hose.get('consent_record')
    consent_documented = None
    if consent is not None:
        if not isinstance(consent, dict) or consent.get('type') not in ('signed_log', 'recorded_radio'):
            raise ValueError('Unsupported consent source')
        if consent.get('official_in_command_id') != hose.get('official_in_command_id'):
            raise ValueError('Consent source command role mismatch')
        if consent.get('vehicle_case_id') != case_id or consent.get('permission') != 'drive_over_hose':
            raise ValueError('Consent source case/permission mismatch')
        consent_documented = True
    return {'format': 'c230231-hose-source-measurement-v1',
            'case_id': case_id, 'source_kind': source_kind,
            'frames': FRAMES, 'rate_hz': 20,
            'first_driven_hose_overlap_frame': next((i for i, v in enumerate(driven_overlap) if v), None),
            'driven_hose_overlap_frames': sum(driven_overlap),
            'ego_center_path_length_m': path_length,
            'hose_unprotected_per_source': not hose['cover_or_ramp_present'],
            'consent_documented_from_command_official': consent_documented,
            'missing_consent_record_means_no_consent': False,
            'hose_radius_is_law': False,
            'legal_verdict': None,
            'original_native_observed': source_kind == 'original_native',
            'delivery_ready': False,
            'source_sha256': {name: sha(root / name) for name in
                              ('actor-sources.jsonl', 'camera-frames.jsonl', 'hose-source.json')}}
