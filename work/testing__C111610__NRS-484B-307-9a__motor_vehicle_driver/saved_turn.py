"""Independent saved-source audit for the red-plus-arrow turn package.

This checks source continuity and decodes every original camera image. It is a
software audit; physical visibility and official signal status need local review.
"""
from __future__ import annotations

import hashlib
import importlib.util
import io
import json
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


def audit_saved_attempt(root, manifest_ref, *, expected_frames=600, fps=20):
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
    try:
        measured = _native.measure_attempt(site, root, manifest['telemetry'])
        case_result = _native.audit_case_measurement(case_suffix, measured)
    except (_native.SourceError, KeyError, TypeError, ValueError) as exc:
        raise SavedSourceError('original turn measurement rejected: ' + str(exc)) from exc
    rows = measured['measurements']
    require(len(rows) == expected_frames, 'original telemetry frame count mismatch')
    require([r['frame'] for r in rows] == list(range(expected_frames)), 'original telemetry frame sequence mismatch')
    cameras = manifest['cameras']
    require(set(cameras) == {'front', 'left', 'right', 'rear'}, 'four original cameras required')
    decoded = {}
    for camera in ('front', 'left', 'right', 'rear'):
        frames = cameras[camera]
        require(isinstance(frames, list) and len(frames) == expected_frames, 'camera frame count mismatch: ' + camera)
        seen_paths = set()
        width_height = None
        for frame, item in enumerate(frames):
            require(item.get('frame') == frame, 'camera frame sequence mismatch: ' + camera)
            ref = item.get('source')
            require(isinstance(ref, dict) and ref.get('path') not in seen_paths, 'camera frame source repeated: ' + camera)
            seen_paths.add(ref['path'])
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
            require(dims == width_height, 'camera dimensions changed: ' + camera)
        decoded[camera] = {'frames': len(frames), 'dimensions': list(width_height)}
    return {'case_suffix': case_suffix, 'manifest_sha256': manifest_ref['sha256'],
            'telemetry_sha256': manifest['telemetry']['sha256'],
            'site_sha256': manifest['site']['sha256'], 'original_frames': expected_frames,
            'decoded_cameras': decoded, 'first_ego_entry_frame': case_result['first_entry_frame'],
            'legal_verdict': None, 'physical_acceptance': False}
