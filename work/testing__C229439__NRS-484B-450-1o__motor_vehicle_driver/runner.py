"""Portable exact-case entrypoint for NRS 484B.450(1)(o).

The operator must supply source-sealed site, device and vehicle records before
Native execution. This CPU entrypoint checks identity and case configuration.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path

from parking import construct_case, sealed_json, validate_sources

ROOT = Path(__file__).resolve().parent


def load_config():
    config = json.loads((ROOT / 'config.json').read_text())
    if (config['law_id'], config['cell_id'], config['actor']) != (
            'NRS-484B-450-1o', 'C229439', 'motor_vehicle_driver'):
        raise ValueError('wrong frozen assignment identity')
    case = config['case']
    if not case['case_id'].startswith('testing__C229439__NRS-484B-450-1o__motor_vehicle_driver__'):
        raise ValueError('wrong exact case identity')
    if case['halt_action'] not in {'park', 'stop', 'stand'} or case['exception'] not in {
            'none', 'traffic_conflict', 'law', 'police_direction', 'device_direction'}:
        raise ValueError('invalid case action or exception')
    if config['rate_hz'] != 20 or config['duration_s'] != 45 or set(config['cameras']) != {'front', 'rear', 'left', 'right'}:
        raise ValueError('capture profile changed')
    return config


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--site-ref')
    parser.add_argument('--device-ref')
    parser.add_argument('--vehicle-ref')
    parser.add_argument('--context-ref')
    parser.add_argument('--output-dir')
    parser.add_argument('--host', default='localhost')
    parser.add_argument('--port', type=int, default=2000)
    args = parser.parse_args()
    config = load_config()
    if args.check:
        print(json.dumps({'case_id': config['case']['case_id'], 'identity_checked': True,
                          'capture_profile_checked': True, 'simulation_started': False}))
        return
    ref_paths = [value or os.environ.get(key) for value, key in (
        (args.site_ref, 'C229439_SITE_REF'),
        (args.device_ref, 'C229439_DEVICE_REF'),
        (args.vehicle_ref, 'C229439_VEHICLE_REF'),
        (args.context_ref, 'C229439_CONTEXT_REF'))]
    if not all(ref_paths) or not args.output_dir:
        raise ValueError('Native execution requires source-sealed site, device and vehicle refs')
    refs = [json.loads(Path(path).read_text()) for path in ref_paths[:3]]
    site, device, vehicle = validate_sources(*refs, config['case'])
    context = sealed_json(json.loads(Path(ref_paths[3]).read_text()))
    observer_ref = context.get('observer_module')
    if not observer_ref or not context.get('camera_pose_review_sha256'):
        raise ValueError('reviewed live context observer and camera poses required')
    observer_path = Path(observer_ref['path']).resolve()
    if hashlib.sha256(observer_path.read_bytes()).hexdigest() != observer_ref['sha256']:
        raise ValueError('live context observer source hash mismatch')
    spec = importlib.util.spec_from_file_location('c229439_context_observer', observer_path)
    observer = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(observer)
    if not callable(getattr(observer, 'observe', None)):
        raise ValueError('live context observer must implement observe')
    import carla
    from native_carla_adapter import NativeParkingAdapter
    from native_capture import capture
    client = carla.Client(args.host, args.port)
    client.set_timeout(20.0)
    world = client.get_world()
    settings = world.get_settings()
    weather = world.get_weather()
    owned = []
    try:
        sync = world.get_settings()
        sync.synchronous_mode = True
        sync.fixed_delta_seconds = 0.05
        world.apply_settings(sync)
        adapter = NativeParkingAdapter(world, carla, owned=owned,
                                       exception_packets=context.get('exception_packets'))
        construct_case(adapter, *refs, config['case'])
        capture(world, carla, adapter, config['case'], site, device,
                observer.observe, args.output_dir, context['reviewed_camera_poses'])
    finally:
        for actor in reversed(owned):
            try:
                actor.destroy()
            except RuntimeError:
                pass
        world.apply_settings(settings)
        world.set_weather(weather)


if __name__ == '__main__':
    main()
