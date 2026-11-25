"""Operator entrypoint for original Native paragraph-(a) right-pass attempts.

Only a hash-bound, source-reviewed map packet can activate this path. CARLA is
loaded at command invocation; importing this module remains CPU portable.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from pass_right_control import make_controller, spawn_four_cameras, spawn_source_actors
from pass_right_live import bind_live_route
from pass_right_route import build_case, load_map_packet
from pass_right_session import run_session

ASSIGNMENT = 'testing__C110264__NRS-484B-210-1__motor_vehicle_driver'


class LazyFrameMap:
    """Write original frame identities after the session freshness check."""

    def __init__(self, path: Path):
        self.path = path
        self.stream = None
        self.index = 0

    def append(self, native_frame: int, elapsed_seconds: float, **extra):
        if self.stream is None:
            self.stream = self.path.open('x')
        row = {'original_index': self.index, 'native_frame_id': native_frame,
               'elapsed_seconds': elapsed_seconds, **extra}
        self.stream.write(json.dumps(row, sort_keys=True) + '\n')
        self.index += 1

    def close(self):
        if self.stream is not None:
            self.stream.close()


def write_source_manifest(world, packet_path: Path, packet_sha256: str,
                          variant: str, attempt: Path, receipt: dict) -> Path:
    """Seal original map, route, binding, trace and four camera source paths."""
    attempt = Path(attempt)
    if (attempt / 'source-manifest.json').exists():
        raise ValueError('retain original Native source manifest')
    packet = load_map_packet(packet_path, packet_sha256)
    if packet.get('diagnostic_fixture') is True:
        raise ValueError('synthetic map cannot become original Native source manifest')
    (attempt / 'map.json').write_bytes(Path(packet_path).read_bytes())
    (attempt / 'route.json').write_text(json.dumps(build_case(packet, variant), sort_keys=True) + '\n')
    binding = bind_live_route(world, packet_path, packet_sha256, variant)
    (attempt / 'live-map-binding.json').write_text(json.dumps(binding, sort_keys=True) + '\n')
    def source(name):
        path = attempt / name
        return {'path': name, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
    cameras = receipt.get('camera_sources')
    if not isinstance(cameras, dict) or set(cameras) != {'front', 'rear', 'left', 'right'}:
        raise ValueError('four original camera sources missing from Native capture')
    manifest = {
        'assignment_id': ASSIGNMENT,
        'case_id': ASSIGNMENT + '__' + variant,
        'variant': variant, 'diagnostic_fixture': False,
        'map': source('map.json'), 'route_request': source('route.json'),
        'live_map_binding': source('live-map-binding.json'),
        'trace': source('trace.json'), 'frame_count': 900,
        'cameras': {name: source(cameras[name]['path']) for name in sorted(cameras)}}
    for name in cameras:
        if manifest['cameras'][name]['sha256'] != cameras[name]['sha256']:
            raise ValueError(name + ' camera changed since original capture')
    output = attempt / 'source-manifest.json'
    output.write_text(json.dumps(manifest, indent=2, sort_keys=True) + '\n')
    return output


def acquire(world, carla_api, *, packet_path: Path, packet_sha256: str,
            variant: str, attempt: Path, setup_role: str = 'primary') -> dict:
    """Execute both source-bound actors, four views, controller and readback."""
    packet = load_map_packet(packet_path, packet_sha256)
    if setup_role not in ('primary', 'fallback1'):
        raise ValueError('unknown reviewed Native setup role')
    setup = packet.get('native_setup' if setup_role == 'primary' else 'fallback_native_setup')
    if setup_role == 'fallback1' and (not isinstance(setup, dict) or
                                      setup.get('reviewed_independently') is not True):
        raise ValueError('independently reviewed fallback Native setup required')
    if setup_role == 'fallback1':
        setup = {key: value for key, value in setup.items() if key != 'reviewed_independently'}
    if not isinstance(setup, dict) or set(setup) != {
            'ego_blueprint_id', 'target_blueprint_id', 'ego_start_s_m',
            'target_start_s_m', 'ego_speed_mps', 'target_speed_mps',
            'camera_mounts'}:
        raise ValueError('reviewed original Native setup required')
    blueprints = world.get_blueprint_library()
    factory = lambda packet, case: spawn_source_actors(
        world, packet, case, blueprint_library=blueprints,
        transform_factory=carla_api.Transform, location_factory=carla_api.Location,
        rotation_factory=carla_api.Rotation,
        ego_blueprint_id=setup['ego_blueprint_id'],
        target_blueprint_id=setup['target_blueprint_id'],
        ego_start_s_m=setup['ego_start_s_m'],
        target_start_s_m=setup['target_start_s_m'])
    frame_map = LazyFrameMap(Path(attempt) / 'frame-map.jsonl')
    try:
        receipt = run_session(
            world, packet_path=packet_path, packet_sha256=packet_sha256,
            variant=variant, attempt=attempt,
            map_reader=lambda native_world: native_world.get_map().to_opendrive().encode('utf-8'),
            spawn_actors=lambda native_world, source, case: factory(source, case),
            spawn_sensors=lambda native_world, ego, target, source, case: spawn_four_cameras(
                native_world, ego, blueprint_library=blueprints,
                transform_factory=carla_api.Transform, location_factory=carla_api.Location,
                rotation_factory=carla_api.Rotation, mounts=setup['camera_mounts']),
            controller_factory=lambda native_world, ego, target, source, case: make_controller(
                ego, target, source, case, control_factory=carla_api.VehicleControl,
                left_signal_mask=int(carla_api.VehicleLightState.LeftBlinker),
                ego_speed_mps=setup['ego_speed_mps'], target_speed_mps=setup['target_speed_mps']),
            frame_map=frame_map,
            left_signal_mask=int(carla_api.VehicleLightState.LeftBlinker))
        write_source_manifest(world, packet_path, packet_sha256, variant,
                              Path(attempt), receipt)
        return receipt
    finally:
        frame_map.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--map-packet', type=Path, required=True)
    parser.add_argument('--map-sha256', required=True)
    parser.add_argument('--variant', choices=('left_signal', 'left_turn', 'neither'), required=True)
    parser.add_argument('--attempt', type=Path, required=True)
    parser.add_argument('--setup-role', choices=('primary', 'fallback1'), default='primary')
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=2000)
    args = parser.parse_args()
    load_map_packet(args.map_packet, args.map_sha256)
    import carla
    client = carla.Client(args.host, args.port)
    client.set_timeout(20)
    result = acquire(client.get_world(), carla, packet_path=args.map_packet,
                     packet_sha256=args.map_sha256, variant=args.variant,
                     attempt=args.attempt, setup_role=args.setup_role)
    print(json.dumps(result, sort_keys=True))


if __name__ == '__main__':
    main()
