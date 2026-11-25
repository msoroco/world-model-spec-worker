"""Audit source provenance for a proposed countdown control and crossing.

This is a preparation audit. A successful synthetic check never establishes
that a Native pedestrian signal or a statutory highway was observed.
"""
import hashlib
import json
from pathlib import Path

from geometry import check as check_geometry


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def audit(attempt, *, require_native=False):
    attempt = Path(attempt)
    context_path = attempt / 'countdown-context.json'
    map_path = attempt / 'road.xodr'
    if not context_path.is_file() or not map_path.is_file():
        raise ValueError('Missing original countdown context or crossing map')
    context = json.loads(context_path.read_text())
    geometry = check_geometry(map_path)
    if context.get('authored_map_sha256') != sha(map_path):
        raise ValueError('Countdown context binds another crossing map')
    if (context.get('crosswalk_id') != geometry['crosswalk_id'] or
            context.get('near_highway_edge_xy_m') != [geometry['near_edge_x_m'], -.65] or
            context.get('highway_span_m') != geometry['road_width_m'] or
            context.get('crossing_forward_xy') != [1, 0]):
        raise ValueError('Countdown context crossing geometry differs')
    kind = context.get('source_kind')
    if kind not in ('synthetic_scene_request', 'native_observation'):
        raise ValueError('Unrecognized countdown context source kind')
    if require_native and kind != 'native_observation':
        raise ValueError('Original Native countdown context required')
    device = context.get('governing_device_evidence')
    supported = False
    if kind == 'native_observation':
        if context.get('display_source_kind') == 'debug_draw_string':
            raise ValueError('Debug text is not a governing pedestrian signal')
        if not isinstance(device, dict):
            raise ValueError('Missing original governing pedestrian device evidence')
        required = ('native_actor_id', 'native_blueprint_id', 'original_pose',
                    'facing_direction_xy', 'crosswalk_id', 'control_readback_path',
                    'control_readback_sha256', 'pixel_audit_path', 'pixel_audit_sha256')
        if any(not device.get(key) for key in required):
            raise ValueError('Incomplete original governing pedestrian device evidence')
        if device['crosswalk_id'] != context['crosswalk_id']:
            raise ValueError('Governing pedestrian device crosswalk differs')
        for path_key, hash_key in (('control_readback_path', 'control_readback_sha256'),
                                   ('pixel_audit_path', 'pixel_audit_sha256')):
            relative = Path(device[path_key])
            if relative.is_absolute() or '..' in relative.parts:
                raise ValueError('Governing device evidence path escapes attempt')
            source = attempt / relative
            if not source.is_file() or sha(source) != device[hash_key]:
                raise ValueError('Missing or changed original governing device evidence')
        readback = json.loads((attempt / device['control_readback_path']).read_text())
        pixels = json.loads((attempt / device['pixel_audit_path']).read_text())
        if (readback.get('native_actor_id') != device['native_actor_id'] or
                readback.get('crosswalk_id') != context['crosswalk_id'] or
                readback.get('pedestrian_signal_governs') is not True or
                pixels.get('digit_legibility_verified') is not True or
                pixels.get('flashing_indication_verified') is not True):
            raise ValueError('Original governing device control or pixel review failed')
        supported = True
    return {'format': 'c10316-governing-context-audit-v1',
            'source_kind': kind, 'context_sha256': sha(context_path),
            'authored_map_sha256': sha(map_path), 'crosswalk_id': context['crosswalk_id'],
            'governing_device_source_verified': supported,
            'statutory_exception_applicability_verified': False,
            'highway_status_verified': False, 'legal_verdict_claimed': False}
