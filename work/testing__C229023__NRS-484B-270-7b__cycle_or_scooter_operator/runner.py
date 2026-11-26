"""Source-gated 20 Hz original capture for the five passing comparisons."""

import argparse
import hashlib
import importlib
import json
import os
from pathlib import Path

from overtake import CASES, construct, require, validate_scene

VIEWS = ('overview', 'approach', 'alongside', 'rear_reference')
ASSIGNMENT = 'testing__C229023__NRS-484B-270-7b__cycle_or_scooter_operator'


def load_scene(packet_path, source_root, case):
    """Resolve every cited original input by bytes before actor creation."""
    raw = Path(packet_path).read_bytes()
    packet = json.loads(raw)
    require(packet.get('case_id') == ASSIGNMENT + '__' + case.case_id,
            'reviewed packet exact case differs')
    require(packet.get('source_kind') == 'reviewed_original_scene',
            'reviewed original scene packet required')
    scene = packet.get('scene')
    require(isinstance(scene, dict), 'reviewed original scene missing')
    for field in ('jurisdiction', 'road_geometry', 'cycle_classification',
                  'wheel_arrangement', 'wheel_diameter', 'moped_exclusion',
                  'operator_control', 'motor_vehicle_classification',
                  'motor_vehicle_occupants', 'passing_side', 'route_geometry'):
        entry = packet.get('sources', {}).get(field)
        require(isinstance(entry, dict), 'source manifest missing: ' + field)
        name = entry.get('path')
        require(isinstance(name, str) and name and not Path(name).is_absolute(),
                'source relative path missing: ' + field)
        root = Path(source_root).resolve()
        target = (root / name).resolve()
        require(target.is_relative_to(root) and target.is_file(),
                'original source file missing: ' + field)
        digest = hashlib.sha256(target.read_bytes()).hexdigest()
        require(digest == entry.get('sha256') == scene.get(field + '_source_sha256'),
                'original source hash differs: ' + field)
    validate_scene(scene, case)
    return scene, hashlib.sha256(raw).hexdigest()


def run(adapter, scene, case, config, output, packet_sha256):
    require(config['selected_case_id'] == ASSIGNMENT + '__' + case.case_id,
            'exact selected case differs')
    require(config['rate_hz'] == 20 and config['frame_count'] == 900 and
            config['duration_s'] == 45 and
            tuple(camera['name'] for camera in config['cameras']) == VIEWS,
            'capture contract differs')
    live_road = adapter.map_opendrive_bytes()
    require(isinstance(live_road, bytes) and
            hashlib.sha256(live_road).hexdigest() ==
            scene['road_geometry_source_sha256'],
            'live road geometry differs from reviewed original source')
    require(adapter.pass_route_readback(scene['cycle_route_xy'],
                                        scene['motor_route_xy']) is True,
            'live passing routes differ from reviewed original geometry')
    built = construct(adapter, scene, case)
    try:
        adapter.begin_four_camera_capture(VIEWS, config['cameras'],
                                          built['owned'], output)
        frames = []
        for _ in range(900):
            frame = adapter.tick()
            require(type(frame) is int and
                    (not frames or frame == frames[-1] + 1),
                    'original frame sequence incomplete')
            frames.append(frame)
            adapter.record_original_pass_readback(frame, built, output)
        adapter.finish_four_camera_capture(output)
        require(adapter.camera_frame_counts() == {view: 900 for view in VIEWS},
                'original four-camera capture incomplete')
        return {'case_id': config['selected_case_id'], 'frame_count': 900,
                'first_frame': frames[0], 'last_frame': frames[-1],
                'reviewed_scene_packet_sha256': packet_sha256,
                'physical_acceptance_claimed': False,
                'legal_judgment': None}
    finally:
        for actor in reversed(built['owned']):
            adapter.destroy(actor)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--output-dir', type=Path)
    parser.add_argument('--scene-packet', type=Path,
                        default=os.getenv('C229023_SCENE_PACKET'))
    parser.add_argument('--source-root', type=Path,
                        default=os.getenv('C229023_SOURCE_ROOT'))
    parser.add_argument('--adapter-module',
                        default=os.getenv('C229023_ADAPTER_MODULE', 'native_adapter'))
    parser.add_argument('--host', default=os.getenv('CARLA_HOST'))
    parser.add_argument('--port', default=os.getenv('CARLA_PORT'))
    args = parser.parse_args()
    config = json.loads((Path(__file__).parent / 'config.json').read_text())
    case = next((item for item in CASES if
                 ASSIGNMENT + '__' + item.case_id == config['selected_case_id']), None)
    require(case is not None, 'unknown selected exact case')
    if args.check:
        print(config['selected_case_id'])
        return
    require(args.output_dir and args.scene_packet and args.source_root and
            args.host and args.port, 'original scene, output and CARLA endpoint required')
    scene, packet_sha256 = load_scene(args.scene_packet, args.source_root, case)
    adapter = importlib.import_module(args.adapter_module).create_adapter(
        config, args.host, int(args.port))
    print(json.dumps(run(adapter, scene, case, config, args.output_dir,
                         packet_sha256), sort_keys=True))


if __name__ == '__main__':
    main()
