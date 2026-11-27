"""Original-source gated Native capture for NRS 484B.270(7)(a)."""

import argparse
import hashlib
import importlib
import json
import os
from pathlib import Path

from interference import CASES, construct, require, validate_scene


ASSIGNMENT = 'testing__C147344__NRS-484B-270-7a__cycle_or_scooter_operator'
VIEWS = ('overview', 'approach', 'reference_corner', 'driver_reference')
SOURCE_FIELDS = ('reviewed_road', 'electric_bicycle_classification',
                 'motor_vehicle_classification', 'route_geometry',
                 'operator_control', 'authored_plan')


def check_config(config):
    require(config.get('law_id') == 'NRS-484B-270-7a' and
            config.get('cell_id') == 'C147344' and
            config.get('actor') == 'cycle_or_scooter_operator' and
            config.get('selected_case_id') in
            {ASSIGNMENT + '__' + item.suffix for item in CASES} and
            config.get('rate_hz') == 20 and
            config.get('duration_s') == 30 and
            tuple(camera.get('name') for camera in config.get('cameras', []))
            == VIEWS, 'exact Class 1 electric-bicycle capture contract differs')
    return True


def load_scene(packet_path, source_root, case):
    """Read independently reviewed source bytes before making any CARLA calls."""
    packet_path = Path(packet_path)
    raw = packet_path.read_bytes()
    packet = json.loads(raw)
    require(packet.get('format') == 'c147344-reviewed-original-scene-v1' and
            packet.get('case_id') == ASSIGNMENT + '__' + case.suffix,
            'exact reviewed original scene packet required')
    scene = packet.get('scene')
    require(isinstance(scene, dict), 'reviewed original scene missing')
    source_root = Path(source_root).resolve()
    sources = packet.get('sources')
    require(isinstance(sources, dict) and set(sources) == set(SOURCE_FIELDS),
            'reviewed source inventory incomplete')
    for field in SOURCE_FIELDS:
        reference = sources[field]
        name = reference.get('path') if isinstance(reference, dict) else None
        require(isinstance(name, str) and name and
                not Path(name).is_absolute(),
                'relative original source path required: ' + field)
        target = (source_root / name).resolve()
        require(target.is_relative_to(source_root) and target.is_file() and
                not target.is_symlink(),
                'original source file missing: ' + field)
        digest = hashlib.sha256(target.read_bytes()).hexdigest()
        require(digest == reference.get('sha256') ==
                scene.get(field + '_source_sha256'),
                'original source hash changed: ' + field)
    validate_scene(scene, case)
    return scene, hashlib.sha256(raw).hexdigest()


def capture(adapter, scene, case, config, output, packet_sha256):
    """Capture 600 joined Native ticks; controller requests never prove motion."""
    check_config(config)
    require(config['selected_case_id'] == ASSIGNMENT + '__' + case.suffix,
            'exact case config changed')
    road = adapter.map_opendrive_bytes()
    require(isinstance(road, bytes) and
            hashlib.sha256(road).hexdigest() ==
            scene['reviewed_road_source_sha256'],
            'live road differs from reviewed original geometry')
    require(adapter.route_readback(scene['routes'],
                                   scene['lane_assignments']) is True,
            'live lane assignments or routes differ')
    built = construct(adapter, scene, case)
    frames = []
    try:
        adapter.begin_four_camera_capture(VIEWS, config['cameras'],
                                          built['owned'], output)
        for _ in range(600):
            frame = adapter.tick()
            require(type(frame) is int and
                    (not frames or frame == frames[-1] + 1),
                    'original Native frame sequence incomplete')
            frames.append(frame)
            adapter.record_original_interaction_readback(frame, built, output)
        adapter.finish_four_camera_capture(output)
        require(adapter.camera_frame_counts() ==
                {name: 600 for name in VIEWS},
                'four-camera original frame counts incomplete')
        require(adapter.native_source_kind() == 'original_native_capture',
                'original Native acquisition provenance missing')
        return {'case_id': config['selected_case_id'],
                'frame_count': len(frames),
                'first_frame': frames[0], 'last_frame': frames[-1],
                'reviewed_scene_packet_sha256': packet_sha256,
                'physical_acceptance_claimed': False,
                'intent_inferred_from_motion': False,
                'legal_judgment': None}
    finally:
        for actor in reversed(built['owned']):
            adapter.destroy(actor)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--output-dir', type=Path)
    parser.add_argument('--scene-packet', type=Path,
                        default=os.getenv('C147344_REVIEWED_SCENE_PACKET'))
    parser.add_argument('--source-root', type=Path,
                        default=os.getenv('C147344_SOURCE_ROOT'))
    parser.add_argument('--adapter-module',
                        default=os.getenv('C147344_ADAPTER_MODULE',
                                          'native_adapter'))
    parser.add_argument('--host', default=os.getenv('CARLA_HOST'))
    parser.add_argument('--port', default=os.getenv('CARLA_PORT'))
    args = parser.parse_args()
    config = json.loads(Path('config.json').read_text())
    check_config(config)
    if args.check:
        print(config['selected_case_id'])
        return
    require(args.output_dir and args.scene_packet and args.source_root and
            args.host and args.port, 'original scene, output and endpoint required')
    case = next(item for item in CASES if
                ASSIGNMENT + '__' + item.suffix == config['selected_case_id'])
    scene, packet_sha256 = load_scene(args.scene_packet,
                                      args.source_root, case)
    adapter = importlib.import_module(args.adapter_module).create_adapter(
        config, args.host, int(args.port))
    from worker_exchange.world_restore import snapshot, restore
    from worker_exchange.native_output import seal_capture
    saved_world = snapshot(adapter.client)
    result = None
    try:
        result = capture(adapter, scene, case, config,
                         args.output_dir, packet_sha256)
    finally:
        restored = restore(adapter.client, saved_world)
    require(restored is not None, 'Native world restoration unverified')
    (args.output_dir / 'capture-runner-result.json').write_text(
        json.dumps(result, indent=2, sort_keys=True) + '\n')
    seal_capture(args.output_dir, frames=600,
                 restoration={'restored': True,
                              'settings_readback': str(restored)},
                 errors=[],
                 encoder_exit_codes={name: 0 for name in VIEWS},
                 context={'reviewed_scene_packet_sha256': packet_sha256})


if __name__ == '__main__':
    main()
