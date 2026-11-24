"""Finalize one saved Native attempt from its original, sealed sources.

The result reports measurements and source identities, never a legal verdict.
"""

import hashlib
import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent


def _module(name, filename):
    spec = importlib.util.spec_from_file_location(name, ROOT / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_AUDIT = _module('center_lane_saved_delivery_audit', 'delivery_audit.py')
_SITE = _module('center_lane_saved_site', 'center_lane_site.py')
_CAMERAS = _module('center_lane_saved_cameras', 'saved_camera_audit.py')


def finalize_saved(attempt_root, expected_case_id, expected_frames, camera_dimensions=None):
    """Reopen the fixed Native receipt and audit its complete saved acquisition."""
    root = Path(attempt_root).resolve()
    if not isinstance(expected_case_id, str) or not expected_case_id:
        raise ValueError('missing expected exact case')
    if type(expected_frames) is not int or expected_frames < 3:
        raise ValueError('missing expected complete frame count')
    receipt_path = root / 'native/capture-receipt.json'
    if not receipt_path.is_file():
        raise ValueError('missing original capture receipt')
    receipt_raw = receipt_path.read_bytes()
    receipt = json.loads(receipt_raw.decode('utf-8'))
    if receipt.get('case_id') != expected_case_id or receipt.get('attempt_id') != root.name:
        raise ValueError('original capture identity mismatch')
    site = _AUDIT._read_bound_json(root, receipt.get('site_source'))
    verified_site = _SITE.validate_site(site)
    if (verified_site['native_map_source'] != receipt.get('lane_design_source') or
            verified_site['highway_review_source'] != receipt.get('highway_context_source')):
        raise ValueError('site and capture source binding differ')
    audited = _AUDIT.audit_saved_delivery(root, receipt)
    if audited['verified_frame_count'] != expected_frames:
        raise ValueError('incomplete original frame count')
    camera_audit = _CAMERAS.audit_original_pngs(root, receipt['frame_map_source'],
                                                expected_frames, camera_dimensions)
    measured = audited['measured']
    if expected_case_id.endswith('__no_merge') and measured['merge_observed']:
        raise ValueError('no-merge case contains observed merge')
    if not expected_case_id.endswith('__no_merge') and not measured['merge_observed']:
        raise ValueError('planned merge case has no observed merge')
    return {
        'case_id': expected_case_id,
        'attempt_id': root.name,
        'capture_receipt_source': {
            'path': 'native/capture-receipt.json',
            'sha256': hashlib.sha256(receipt_raw).hexdigest(),
        },
        'site_source': receipt['site_source'],
        'original_trace': receipt['original_trace'],
        'frame_map_source': receipt['frame_map_source'],
        'verified_frame_count': expected_frames,
        'decoded_camera_images': camera_audit['decoded_camera_images'],
        'distance_m': measured['distance_m'],
        'distance_ft': measured['distance_ft'],
        'turn_frame': measured['turn_frame'],
        'merge_frame': measured['merge_frame'],
        'merge_observed': measured['merge_observed'],
        'censored': measured['censored'],
        'measurement_convention': measured['measurement_convention'],
        'physical_acceptance': None,
        'legal_judgment': None,
    }
