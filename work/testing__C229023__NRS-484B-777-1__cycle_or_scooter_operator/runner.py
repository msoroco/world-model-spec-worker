"""Source-gated Native 20 Hz cycle pass capture for NRS 484B.777(1)."""

import argparse
import hashlib
import importlib
import json
import os
from pathlib import Path

from rightside import CASES, SOURCE_ROLES, construct, need, validate_scene


AID = 'testing__C229023__NRS-484B-777-1__cycle_or_scooter_operator'
VIEWS = ('overview', 'approach', 'reference_corner', 'driver_reference')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_scene(packet_path, source_root, case):
    packet_path = Path(packet_path).resolve()
    packet = json.loads(packet_path.read_text())
    need(packet.get('case_id') == AID + '__' + case.name and
         packet.get('source_kind') == 'reviewed_original_scene',
         'reviewed original exact scene packet required')
    scene = packet.get('scene')
    need(isinstance(scene, dict), 'reviewed original scene missing')
    refs = packet.get('sources', {})
    root = Path(source_root).resolve()
    for role in SOURCE_ROLES:
        entry = refs.get(role)
        need(isinstance(entry, dict) and isinstance(entry.get('path'), str) and
             entry['path'] and not Path(entry['path']).is_absolute(),
             'original source reference missing: ' + role)
        target = (root / entry['path']).resolve()
        need(target.is_relative_to(root) and target.is_file() and
             sha(target) == entry.get('sha256') == scene.get(role + '_source_sha256'),
             'reviewed original source changed: ' + role)
    validate_scene(scene, case)
    return scene, sha(packet_path)


def seal_original(output, scene, packet_sha256, camera_counts):
    output = Path(output).resolve()
    need(output.is_dir(), 'original attempt missing')
    context = output / 'scene-context.json'
    need(not context.exists(), 'retain prior original scene context')
    context.write_text(json.dumps({**scene, 'reviewed_scene_packet_sha256': packet_sha256},
                                  indent=2, sort_keys=True) + '\n')
    names = ('config.json', 'scene-context.json', 'rightside-readback.jsonl',
             'trace.jsonl', 'video_frames.jsonl') + tuple(name + '.mkv' for name in VIEWS)
    files = {}
    for name in names:
        target = output / name
        need(target.is_file() and not target.is_symlink(),
             'original capture source missing: ' + name)
        files[name] = {'sha256': sha(target)}
    destination = output / 'original-sources.json'
    need(not destination.exists(), 'retain prior original source manifest')
    destination.write_text(json.dumps({
        'source_kind': 'original_native_capture', 'accepted_original_source': True,
        'reviewed_scene_packet_sha256': packet_sha256,
        'frame_count': 900, 'camera_frame_counts': camera_counts, 'files': files,
    }, indent=2, sort_keys=True) + '\n')
    return sha(destination)


def run(adapter, scene, case, config, output, packet_sha256):
    need(config['selected_case_id'] == AID + '__' + case.name,
         'exact selected case differs')
    need(config['rate_hz'] == 20 and config['duration_s'] == 45 and
         config['frame_count'] == 900 and
         tuple(camera['name'] for camera in config['cameras']) == VIEWS,
         'capture rate, duration or camera contract differs')
    need(hashlib.sha256(adapter.map_opendrive_bytes()).hexdigest() ==
         scene['road_geometry_source_sha256'],
         'live Native roadway differs from reviewed original geometry')
    need(adapter.pass_route_readback(scene['cycle_route_xy'], scene['other_route_xy']),
         'live passing routes differ from reviewed original scene')
    built = construct(adapter, scene, case)
    try:
        adapter.begin_four_camera_capture(VIEWS, config['cameras'], built['owned'], output)
        frames = []
        for _ in range(900):
            frame = adapter.tick()
            need(type(frame) is int and (not frames or frame == frames[-1] + 1),
                 'original Native frame sequence incomplete')
            frames.append(frame)
            adapter.record_original_rightside_readback(frame, built, output)
        adapter.finish_four_camera_capture(output)
        counts = adapter.camera_frame_counts()
        need(counts == {name: 900 for name in VIEWS},
             'four original camera frame counts incomplete')
        need(adapter.native_source_kind() == 'original_native_capture',
             'original Native acquisition provenance missing')
        source_sha = seal_original(output, scene, packet_sha256, counts)
        return {'case_id': config['selected_case_id'], 'frame_count': 900,
                'first_frame': frames[0], 'last_frame': frames[-1],
                'original_sources_sha256': source_sha,
                'physical_acceptance_claimed': False, 'legal_judgment': None}
    finally:
        for actor in reversed(built['owned']):
            adapter.destroy(actor)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--output-dir', type=Path)
    parser.add_argument('--scene-packet', type=Path, default=os.getenv('C229023_7771_SCENE_PACKET'))
    parser.add_argument('--source-root', type=Path, default=os.getenv('C229023_7771_SOURCE_ROOT'))
    parser.add_argument('--adapter-module', default=os.getenv('C229023_7771_ADAPTER_MODULE',
                                                            'native_adapter'))
    parser.add_argument('--host', default=os.getenv('CARLA_HOST'))
    parser.add_argument('--port', default=os.getenv('CARLA_PORT'))
    args = parser.parse_args()
    config = json.loads((Path(__file__).parent / 'config.json').read_text())
    selected = config['selected_case_id']
    case = next((item for item in CASES if AID + '__' + item.name == selected), None)
    need(case is not None and config['assignment_id'] == AID and
         config['law_id'] == 'NRS-484B-777-1' and config['cell_id'] == 'C229023',
         'exact runner identity differs')
    if args.check:
        print('exact right-side runner static check passed: ' + selected)
        return
    need(args.scene_packet is not None and args.source_root is not None and
         args.host and args.port and args.output_dir is not None,
         'reviewed Native scene, host, port and output required')
    scene, packet_sha = load_scene(args.scene_packet, args.source_root, case)
    adapter = importlib.import_module(args.adapter_module).create_adapter(
        config, args.host, int(args.port))
    from worker_exchange.world_restore import snapshot, restore
    from worker_exchange.native_output import seal_capture
    world = snapshot(adapter.client)
    failure = None
    result = None
    restoration = None
    try:
        result = run(adapter, scene, case, config, args.output_dir, packet_sha)
    except Exception as error:
        failure = error
    finally:
        try:
            restoration = restore(adapter.client, world)
        except Exception as error:
            failure = failure or error
    if failure is not None:
        args.output_dir.mkdir(parents=True, exist_ok=True)
        (args.output_dir / 'native-run-status.json').write_text(json.dumps({
            'errors': [str(failure)], 'restoration': restoration,
            'physical_acceptance_claimed': False}, indent=2) + '\n')
        raise failure
    codes = adapter.encoder_exit_codes()
    need(set(codes) == set(VIEWS) and all(value == 0 for value in codes.values()),
         'four original camera encoders failed to close')
    seal_capture(args.output_dir, frames=900, restoration=restoration,
                 errors=[], encoder_exit_codes=codes,
                 context={'reviewed_scene_packet_sha256': packet_sha,
                          'case_id': selected})
    print(json.dumps(result, sort_keys=True))


if __name__ == '__main__':
    main()
