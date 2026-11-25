"""Operator entrypoint for original Native paragraph-(a) right-pass attempts.

Only a hash-bound, source-reviewed map packet can activate this path. CARLA is
loaded at command invocation; importing this module remains CPU portable.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from pass_right_control import make_controller, spawn_four_cameras, spawn_source_actors
from pass_right_route import load_map_packet
from pass_right_session import run_session


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


def acquire(world, carla_api, *, packet_path: Path, packet_sha256: str,
            variant: str, attempt: Path) -> dict:
    """Execute both source-bound actors, four views, controller and readback."""
    packet = load_map_packet(packet_path, packet_sha256)
    setup = packet.get('native_setup')
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
        return run_session(
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
    finally:
        frame_map.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--map-packet', type=Path, required=True)
    parser.add_argument('--map-sha256', required=True)
    parser.add_argument('--variant', choices=('left_signal', 'left_turn', 'neither'), required=True)
    parser.add_argument('--attempt', type=Path, required=True)
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=2000)
    args = parser.parse_args()
    load_map_packet(args.map_packet, args.map_sha256)
    import carla
    client = carla.Client(args.host, args.port)
    client.set_timeout(20)
    result = acquire(client.get_world(), carla, packet_path=args.map_packet,
                     packet_sha256=args.map_sha256, variant=args.variant,
                     attempt=args.attempt)
    print(json.dumps(result, sort_keys=True))


if __name__ == '__main__':
    main()
