"""Saved-source checks for the three NRS 484B.210(1)(a) cases.

This is an independent CPU audit of original source packets, not a legal verdict or
proof that a later physical run was accepted. Paths in the attempt are relative to
its directory and are constrained there before bytes are opened.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from pass_right_measure import load_sealed_trace, observe
from pass_right_route import build_case, load_map_packet
from pass_right_media import audit_cameras

ASSIGNMENT = 'testing__C110264__NRS-484B-210-1__motor_vehicle_driver'
VARIANTS = {'left_signal', 'left_turn', 'neither'}
CAMERAS = {'front', 'rear', 'left', 'right'}


def _source(root: Path, item: dict, label: str) -> tuple[Path, str]:
    if not isinstance(item, dict) or set(item) != {'path', 'sha256'}:
        raise ValueError(label + ' source path and sha256 required')
    path = (root / item['path']).resolve()
    if root.resolve() not in path.parents or not path.is_file():
        raise ValueError(label + ' source outside saved attempt or missing')
    expected = item['sha256']
    if not isinstance(expected, str) or len(expected) != 64:
        raise ValueError(label + ' source sha256 malformed')
    if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
        raise ValueError(label + ' source sha256 mismatch')
    return path, expected


def audit_case(root: Path, manifest: dict) -> dict:
    if manifest.get('assignment_id') != ASSIGNMENT:
        raise ValueError('assignment identity mismatch')
    case_id = manifest.get('case_id')
    variant = manifest.get('variant')
    if variant not in VARIANTS or case_id != ASSIGNMENT + '__' + variant:
        raise ValueError('exact case identity mismatch')
    if manifest.get('diagnostic_fixture') is not False:
        raise ValueError('diagnostic or unmarked source cannot prove saved attempt')
    map_path, map_sha = _source(root, manifest.get('map'), 'map')
    trace_path, trace_sha = _source(root, manifest.get('trace'), 'trace')
    request_path, request_sha = _source(root, manifest.get('route_request'), 'route request')
    packet = load_map_packet(map_path, map_sha)
    requested = json.loads(request_path.read_text())
    if requested != build_case(packet, variant):
        raise ValueError('route request differs from source map construction')
    binding_path, binding_sha = _source(root, manifest.get('live_map_binding'), 'live map binding')
    binding = json.loads(binding_path.read_text())
    if (binding.get('case_variant') != variant or
            binding.get('map_name') != packet.get('map_name') or
            binding.get('map_packet_sha256') != map_sha or
            binding.get('loaded_opendrive_sha256') != packet.get('source_opendrive_sha256') or
            binding.get('route_request') != requested or
            binding.get('requires_live_actor_and_camera_checks') is not True or
            binding.get('physical_acceptance_claimed') is not False):
        raise ValueError('saved live map binding differs from source map or route')
    trace = load_sealed_trace(trace_path, trace_sha)
    road = trace.get('road', {})
    if road.get('intersection_s_m') != packet['intersection_s_m']:
        raise ValueError('trace and map intersection bounds differ')
    if road.get('actor_half_width_m') != packet['actor_half_width_m']:
        raise ValueError('trace and map actor footprint differs')
    if (trace.get('fps') != 20 or len(trace.get('frames', [])) != 900 or
            manifest.get('frame_count') != 900):
        raise ValueError('original trace frame count or rate mismatch')
    first_native = trace['frames'][0].get('native_frame_id')
    if not isinstance(first_native, int):
        raise ValueError('original Native frame map missing')
    for index, frame in enumerate(trace['frames']):
        if frame.get('native_frame_id') != first_native + index:
            raise ValueError('original Native frame map gap')
        cameras_at_frame = frame.get('camera_frame_ids')
        if (not isinstance(cameras_at_frame, dict) or set(cameras_at_frame) != CAMERAS or
                any(cameras_at_frame[name] != first_native + index for name in CAMERAS)):
            raise ValueError('original four-camera frame join mismatch')
    cameras = manifest.get('cameras')
    if not isinstance(cameras, dict) or set(cameras) != CAMERAS:
        raise ValueError('all four camera sources required')
    for name in sorted(CAMERAS):
        _source(root, cameras[name], name + ' camera')
    measured = observe(trace)
    if measured['target_left_signal_during_pass'] != (variant == 'left_signal'):
        raise ValueError('observed signal differs from exact variant')
    if measured['target_left_motion_during_pass'] != (variant == 'left_turn'):
        raise ValueError('observed turn differs from exact variant')
    first = trace['frames'][0]
    return {
        'format': 'worker-right-pass-source-audit', 'case_id': case_id,
        'assignment_id': ASSIGNMENT, 'variant': variant,
        'map_sha256': map_sha, 'trace_sha256': trace_sha,
        'route_request_sha256': request_sha, 'live_map_binding_sha256': binding_sha,
        'loaded_opendrive_sha256': binding['loaded_opendrive_sha256'],
        'camera_sha256': {name: cameras[name]['sha256'] for name in sorted(CAMERAS)},
        'frame_count': len(trace['frames']), 'fps': 20,
        'initial_ego_s_m': first['ego_s_m'],
        'initial_target_s_m': first['target_s_m'],
        'initial_target_lateral_m': first['target_lateral_m'],
        'initial_ego_speed_mps': first['ego_speed_mps'],
        'initial_target_speed_mps': first['target_speed_mps'],
        'actor_half_width_m': packet['actor_half_width_m'],
        'ego_path_s_lateral_m': requested['ego_path_s_lateral_m'],
        'intersection_s_m': packet['intersection_s_m'],
        'measurement': measured, 'legal_outcome': 'unresolved',
        'physical_acceptance_claimed': False,
    }


def audit_delivery(root: Path, manifest: dict, *, diagnostic_profile=None) -> dict:
    """Require source audit plus a complete independent decode of all cameras."""
    source_audit = audit_case(root, manifest)
    decoded = audit_cameras(root, manifest['cameras'], profile=diagnostic_profile)
    source_audit['full_original_camera_decode'] = True
    source_audit['production_camera_profile_verified'] = diagnostic_profile is None
    source_audit['camera_pixel_sha256'] = {
        name: decoded[name]['full_pixel_sha256'] for name in sorted(CAMERAS)}
    source_audit['physical_visibility_confirmed'] = False
    return source_audit


def audit_comparison(a: dict, b: dict, comparison_id: str) -> dict:
    pairs = {
        'left_signal_presence': {'left_signal', 'neither'},
        'left_turn_motion_presence': {'left_turn', 'neither'},
    }
    if comparison_id not in pairs or {a.get('variant'), b.get('variant')} != pairs[comparison_id]:
        raise ValueError('exact comparison case pair mismatch')
    for record in (a, b):
        if record.get('format') != 'worker-right-pass-source-audit' or record.get('assignment_id') != ASSIGNMENT:
            raise ValueError('comparison needs source-audited cases')
        if record.get('physical_acceptance_claimed') is not False:
            raise ValueError('unsupported physical acceptance claim')
    for field in ('map_sha256', 'loaded_opendrive_sha256', 'intersection_s_m', 'fps', 'frame_count',
                  'ego_path_s_lateral_m', 'initial_ego_s_m', 'initial_target_s_m',
                  'initial_target_lateral_m', 'initial_ego_speed_mps',
                  'initial_target_speed_mps', 'actor_half_width_m'):
        if a[field] != b[field]:
            raise ValueError('fixed comparison condition differs: ' + field)
    for record in (a, b):
        m = record['measurement']
        if not m['right_pass_observed'] or not m['intersection_crossed_during_pass']:
            raise ValueError('comparison lacks observed intersection right pass')
        if m['target_left_signal_during_pass'] != (record['variant'] == 'left_signal'):
            raise ValueError('comparison signal mismatch')
        if m['target_left_motion_during_pass'] != (record['variant'] == 'left_turn'):
            raise ValueError('comparison turn mismatch')
    return {
        'format': 'worker-right-pass-comparison-audit',
        'comparison_id': comparison_id,
        'case_ids': sorted([a['case_id'], b['case_id']]),
        'fixed_source_map_sha256': a['map_sha256'],
        'observed_difference': 'target_left_signal_during_pass' if comparison_id == 'left_signal_presence' else 'target_left_motion_during_pass',
        'legal_outcome': 'unresolved', 'physical_acceptance_claimed': False,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', type=Path)
    parser.add_argument('--manifest', type=Path)
    parser.add_argument('--attempt-a', type=Path)
    parser.add_argument('--manifest-a', type=Path)
    parser.add_argument('--attempt-b', type=Path)
    parser.add_argument('--manifest-b', type=Path)
    parser.add_argument('--comparison-id')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--full-media', action='store_true')
    args = parser.parse_args()
    if args.attempt and args.manifest and not args.comparison_id:
        loaded = json.loads(args.manifest.read_text())
        result = audit_delivery(args.attempt, loaded) if args.full_media else audit_case(args.attempt, loaded)
    elif all((args.attempt_a, args.manifest_a, args.attempt_b, args.manifest_b, args.comparison_id)):
        audit_function = audit_delivery if args.full_media else audit_case
        a = audit_function(args.attempt_a, json.loads(args.manifest_a.read_text()))
        b = audit_function(args.attempt_b, json.loads(args.manifest_b.read_text()))
        result = audit_comparison(a, b, args.comparison_id)
    else:
        parser.error('choose one case attempt or one exact comparison')
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + '\n')


if __name__ == '__main__':
    main()
