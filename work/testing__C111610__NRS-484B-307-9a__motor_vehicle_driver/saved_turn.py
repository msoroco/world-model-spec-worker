"""Independent saved-source audit for the red-plus-arrow turn package.

This checks source continuity and decodes every original camera image. It is a
software audit; physical visibility and official signal status need local review.
"""
from __future__ import annotations

import hashlib
import importlib.util
import io
import json
import math
from pathlib import Path

from PIL import Image


_spec = importlib.util.spec_from_file_location('c111610_native_turn', Path(__file__).with_name('native_turn.py'))
_native = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_native)


class SavedSourceError(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise SavedSourceError(message)


def source_bytes(root, ref):
    base = Path(root).resolve()
    require(isinstance(ref, dict) and isinstance(ref.get('path'), str) and isinstance(ref.get('sha256'), str), 'source reference missing')
    path = (base / ref['path']).resolve()
    require(path.is_relative_to(base), 'source escapes attempt root')
    require(path.is_file(), 'original source missing: ' + ref['path'])
    raw = path.read_bytes()
    require(hashlib.sha256(raw).hexdigest() == ref['sha256'], 'original source hash mismatch: ' + ref['path'])
    return raw


def audit_saved_attempt(root, manifest_ref, *, expected_frames=600, fps=20,
                        diagnostic=False):
    """Return a source-bound, nonacceptance measurement for one saved attempt.

    The manifest joins the site, original telemetry and every original camera
    frame by the same zero-based frame number. A supplied expected_frames option
    permits short CPU fixtures; production callers use the 600-frame default.
    """
    require(isinstance(expected_frames, int) and expected_frames > 0, 'invalid expected frame count')
    require(fps == 20, 'capture fps must be 20')
    manifest = json.loads(source_bytes(root, manifest_ref))
    case_suffix = manifest['case_suffix']
    require(case_suffix in ('yield_pedestrian', 'continue_pedestrian', 'clear_crosswalk_turn',
                            'wrong_movement', 'yield_other_traffic', 'continue_other_traffic'), 'unknown exact case')
    require(manifest['fps'] == fps and manifest['duration_frames'] == expected_frames, 'manifest timing mismatch')
    site = json.loads(source_bytes(root, manifest['site']))
    profile = json.loads(source_bytes(root, manifest['camera_profile']))
    if not diagnostic:
        require(expected_frames == 600, 'delivery requires 600 original frames')
        require('frame_map' in manifest, 'original Native frame map missing')
        attestation = manifest.get('native_source_attestation')
        require(isinstance(attestation, dict) and
                attestation.get('native_origin') is True and
                attestation.get('site_sha256') == manifest['site']['sha256'] and
                isinstance(attestation.get('source_ref'), str) and
                bool(attestation['source_ref']),
                'original Native source attestation missing or stale')
        require(site.get('source_kind') == 'original_native_site_review',
                'reviewed original site provenance missing')
        adapter_ref = site.get('adapter_source')
        require(isinstance(adapter_ref, dict) and
                attestation.get('source_ref') == adapter_ref.get('path') and
                attestation.get('adapter_sha256') == adapter_ref.get('sha256'),
                'reviewed original adapter binding missing or stale')
        source_bytes(root, adapter_ref)
    require(profile.get('fps') == fps and profile.get('duration_frames') == expected_frames and
            profile.get('cameras') == ['overview', 'approach', 'reference_corner', 'driver_reference'], 'camera profile mismatch')
    require(set(profile.get('dimensions', {})) == {'overview', 'approach', 'reference_corner', 'driver_reference'},
            'camera profile dimensions missing')
    try:
        measured = _native.measure_attempt(site, root, manifest['telemetry'])
        case_result = _native.audit_case_measurement(case_suffix, measured)
    except (_native.SourceError, KeyError, TypeError, ValueError) as exc:
        raise SavedSourceError('original turn measurement rejected: ' + str(exc)) from exc
    rows = measured['measurements']
    require(len(rows) == expected_frames, 'original telemetry frame count mismatch')
    require([r['frame'] for r in rows] == list(range(expected_frames)), 'original telemetry frame sequence mismatch')
    if 'frame_map' in manifest:
        frame_map = json.loads(source_bytes(root, manifest['frame_map']))
        require(isinstance(frame_map, list) and len(frame_map) == expected_frames,
                'original Native frame map incomplete')
        first_native_time = None
        last_native_frame = None
        for index, entry in enumerate(frame_map):
            frame = entry.get('native_frame')
            time = entry.get('native_elapsed_s')
            require(entry.get('frame') == index and type(frame) is int and
                    type(time) in (int, float) and math.isfinite(time),
                    'original Native frame map identity invalid')
            if first_native_time is None:
                first_native_time = time
            require((last_native_frame is None or frame == last_native_frame + 1) and
                    abs(time - first_native_time - index / fps) <= .001,
                    'original Native frame map clock gap')
            last_native_frame = frame
    cameras = manifest['cameras']
    require(set(cameras) == {'overview', 'approach', 'reference_corner', 'driver_reference'}, 'four original cameras required')
    decoded = {}
    all_camera_paths = set()
    for camera in ('overview', 'approach', 'reference_corner', 'driver_reference'):
        frames = cameras[camera]
        require(isinstance(frames, list) and len(frames) == expected_frames, 'camera frame count mismatch: ' + camera)
        seen_paths = set()
        width_height = None
        for frame, item in enumerate(frames):
            require(item.get('frame') == frame, 'camera frame sequence mismatch: ' + camera)
            ref = item.get('source')
            require(isinstance(ref, dict) and ref.get('path') not in seen_paths, 'camera frame source repeated: ' + camera)
            require(ref['path'] not in all_camera_paths,
                    'original camera source reused across views')
            seen_paths.add(ref['path'])
            all_camera_paths.add(ref['path'])
            raw = source_bytes(root, ref)
            try:
                with Image.open(io.BytesIO(raw)) as image:
                    require(image.format == 'PNG', 'camera source is not PNG: ' + camera)
                    image.load()
                    dims = image.size
                    require(dims[0] > 0 and dims[1] > 0, 'camera dimensions invalid: ' + camera)
            except (OSError, ValueError) as exc:
                raise SavedSourceError('camera image decode failed: ' + camera) from exc
            if width_height is None:
                width_height = dims
            require(dims == width_height and list(dims) == profile['dimensions'][camera],
                    'camera dimensions changed: ' + camera)
        decoded[camera] = {'frames': len(frames), 'dimensions': list(width_height)}
    entry = measured['first_ego_entry']
    approach = [row for row in rows if row['frame'] <= entry['frame']]
    pedestrian_at_approach = any(row['pedestrian_inside_adjacent_crosswalk'] and
                                 row['pedestrian_lawful_context'] for row in approach)
    traffic_at_approach = any(row['other_traffic_lawfully_in_intersection'] for row in approach)
    occupied_at_entry = ((entry['pedestrian_inside_adjacent_crosswalk'] and entry['pedestrian_lawful_context']) or
                         entry['other_traffic_lawfully_in_intersection'])
    comparison_row = {
        'case_suffix': case_suffix, 'duration_frames': expected_frames,
        'original_signal_frames': len(rows), 'first_ego_entry': {'frame': entry['frame']},
        'actual_route': 'arrow_turn' if entry['ego_route_lane_id'] == site['arrow_destination_lane_id'] else 'straight',
        'arrow_direction': site['arrow_direction'],
        'pedestrian_lawfully_inside_at_approach': pedestrian_at_approach,
        'other_traffic_lawfully_in_intersection_at_approach': traffic_at_approach,
        'held_until_clear': (pedestrian_at_approach or traffic_at_approach) and not occupied_at_entry,
        'camera_profile_sha256': manifest['camera_profile']['sha256'],
        'map_sha256': site['original_sources']['map']['sha256'],
        'ego_signal_sha256': site['original_sources']['ego_signal']['sha256'],
        'opposing_signal_sha256': site['original_sources']['opposing_signal']['sha256'],
        'crosswalk_sha256': site['original_sources']['crosswalk']['sha256'],
        'pedestrian_permission_sha256': site['original_sources']['pedestrian_permission']['sha256'],
    }
    return {'case_suffix': case_suffix, 'manifest_sha256': manifest_ref['sha256'],
            'telemetry_sha256': manifest['telemetry']['sha256'],
            'site_sha256': manifest['site']['sha256'], 'original_frames': expected_frames,
            'decoded_cameras': decoded, 'first_ego_entry_frame': case_result['first_entry_frame'],
            'comparison_row': comparison_row, 'legal_verdict': None, 'physical_acceptance': False}
