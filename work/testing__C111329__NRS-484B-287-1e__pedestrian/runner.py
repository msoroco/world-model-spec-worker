"""Source-gated exact diagonal pedestrian Native runner.

The local operator must bind an actual C111329 map, official diagonal device,
and four original RGB sensors. Offline --check does not claim those exist.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path

from diagonal_crossing import advance_walker, spawn_walker
from native_capture import capture
from reviewed_site import validate_reviewed_site


def check(root=None):
    root = Path(root or Path(__file__).resolve().parent)
    config = json.loads((root / 'config.json').read_text())
    plan_bytes = (root / 'case-plan.json').read_bytes()
    if hashlib.sha256(plan_bytes).hexdigest() != config.get('plan_sha256'):
        raise ValueError('exact C111329 case plan changed')
    case_id = config.get('selected_case_id')
    planned = next((row for row in json.loads(plan_bytes)['cases']
                    if row['case_id'] == case_id), None)
    if planned is None or planned['scenario_parameters'] != config.get('scenario_parameters'):
        raise ValueError('exact C111329 case parameters changed')
    if (config.get('rate_hz') != 20 or config.get('duration_s') != 45 or
            config.get('required_atoms') != [] or config.get('source_packets') != []):
        raise ValueError('exact 900-tick 20 Hz capture contract changed')
    required = [('overview', 1920, 1080), ('approach', 1280, 720),
                ('reference_corner', 1280, 720), ('driver_reference', 1280, 720)]
    cameras = config.get('cameras', [])
    if [(c.get('name'), c.get('width'), c.get('height')) for c in cameras] != required:
        raise ValueError('four original camera profiles changed')
    return config


def _operator():
    path_text = os.environ.get('SCENARIO_C111329_ORIGINAL_OPERATOR')
    digest = os.environ.get('SCENARIO_C111329_ORIGINAL_OPERATOR_SHA256')
    if not path_text or not digest:
        raise ValueError('source-reviewed C111329 Native operator is required')
    path = Path(path_text).resolve(strict=True)
    if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
        raise ValueError('source-reviewed C111329 Native operator hash changed')
    spec = importlib.util.spec_from_file_location('c111329_original_operator', path)
    if spec is None or spec.loader is None:
        raise ValueError('source-reviewed C111329 operator cannot load')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def run(output_dir, host, port):
    config = check()
    output = Path(output_dir).resolve()
    repo = next((parent.parent for parent in Path(__file__).resolve().parents
                 if parent.name == '.runtime-work'), None)
    if repo is None:
        raise ValueError('Native runner must execute from materialized .runtime-work bundle')
    if not output.is_dir() or not output.is_relative_to((repo / '.runtime-work').resolve()):
        raise ValueError('Native attempt must be materialized under .runtime-work')
    operator = _operator()
    import carla
    client = carla.Client(host, port)
    client.set_timeout(30)
    world = client.get_world()
    previous = world.get_settings()
    binding = operator.bind_original(world=world, case_id=config['selected_case_id'],
                                     attempt=output)
    for name in ('site', 'device_reader', 'camera_frame_reader', 'camera_image_reader',
                 'crossing_polygon', 'program_device', 'release'):
        if name not in binding:
            raise ValueError('original Native operator binding missing: ' + name)
    site = binding['site']
    validate_reviewed_site(site)
    actor = None
    try:
        settings = world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = .05
        settings.no_rendering_mode = False
        world.apply_settings(settings)
        actor, plan = spawn_walker(world, site, carla_module=carla)
        route_index = 1
        mode = config['scenario_parameters']['governing_device_instruction']
        def before_tick(index):
            nonlocal route_index
            expected = ('diagonal_dont_walk' if mode == 'diagonal_dont_walk' or
                        (mode == 'diagonal_walk_then_dont_walk' and index >= 450)
                        else 'diagonal_walk')
            binding['program_device'](expected, index)
            route_index = advance_walker(actor, plan, route_index, 1.25,
                                         carla_module=carla)
        def walker_reader(snapshot):
            position = actor.get_location()
            return {'source_kind': 'native_walker_readback',
                    'original_frame': snapshot.frame, 'walker_id': actor.id,
                    'center_xy': [float(position.x), float(position.y)]}
        return capture(world, site, config['selected_case_id'], output,
                       walker_reader, binding['device_reader'],
                       binding['camera_frame_reader'], binding['crossing_polygon'],
                       diagnostic=False, attest_original=True,
                       camera_image_reader=binding['camera_image_reader'],
                       before_tick=before_tick)
    finally:
        if actor is not None:
            actor.destroy()
        try:
            binding['release']()
        finally:
            world.apply_settings(previous)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--output-dir')
    parser.add_argument('--host')
    parser.add_argument('--port', type=int)
    args = parser.parse_args()
    config = check()
    if args.check:
        print(config['selected_case_id'] + ': exact source-gated offline check passed')
        return
    if not args.output_dir or not args.host or not args.port:
        raise ValueError('Native output, host and port required')
    run(args.output_dir, args.host, args.port)


if __name__ == '__main__':
    main()
