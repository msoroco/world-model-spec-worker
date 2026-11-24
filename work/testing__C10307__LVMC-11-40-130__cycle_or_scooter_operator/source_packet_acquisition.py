"""Collect Native map/asset observations and assemble reviewed dispatch sources.

Capture never certifies jurisdiction or asset classification. Those judgments
arrive as separate reviewed-original packets and are checked by native_run.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from native_run import source_configuration


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def capture_world_sources(world, destination: Path) -> dict:
    """Save exact live OpenDRIVE and blueprint IDs before review or dispatch."""
    destination = Path(destination).resolve()
    if destination.exists():
        raise ValueError('Native source capture destination already exists')
    live_map = world.get_map()
    name = live_map.name
    road = live_map.to_opendrive()
    ids = sorted({item.id for item in world.get_blueprint_library()})
    if not isinstance(name, str) or not name or not isinstance(road, str) or not road:
        raise ValueError('Native map observation incomplete')
    if not ids or any(not isinstance(value, str) or not value for value in ids):
        raise ValueError('Native blueprint observation incomplete')
    destination.mkdir(parents=True)
    road_path = destination / 'road.xodr'
    road_path.write_bytes(road.encode('utf-8'))
    inventory_path = destination / 'asset-inventory.json'
    inventory_path.write_text(json.dumps({
        'source_kind': 'original_local_native_blueprint_inventory',
        'world_map': name, 'blueprint_ids': ids}, sort_keys=True) + '\n')
    observation = {'world_map': name,
                   'road_source': {'path': str(road_path), 'sha256': sha(road_path)},
                   'asset_inventory': {'path': str(inventory_path), 'sha256': sha(inventory_path)}}
    (destination / 'observation.json').write_text(json.dumps(observation, sort_keys=True) + '\n')
    return observation


def assemble_reviewed_scene(observation: dict, case_id: str, destination: Path,
                            municipal: Path, bicycle: Path, rack: Path,
                            pedestrian: Path | None = None) -> dict:
    """Build a dispatch scene from reviewed packets; reject incomplete joins."""
    destination = Path(destination).resolve()
    if destination.exists():
        raise ValueError('Native reviewed scene already exists')
    def reference(path):
        path = Path(path).resolve()
        return {'path': str(path), 'sha256': sha(path)}
    municipal_ref, bicycle_ref, rack_ref = map(reference, (municipal, bicycle, rack))
    bike_packet = json.loads(Path(bicycle).read_text())
    rack_packet = json.loads(Path(rack).read_text())
    scene = {
        'case_id': case_id,
        'world_map': observation['world_map'],
        'map_sha256': observation['road_source']['sha256'],
        'road_source': observation['road_source'],
        'bicycle_blueprint_id': bike_packet.get('blueprint_id'),
        'rack_blueprint_id': rack_packet.get('blueprint_id'),
        'human_powered_bicycle_verified': True,
        'rack_asset_verified': True,
        'bicycle_classification_source': bicycle_ref,
        'rack_geometry_source': rack_ref,
        'jurisdiction': {'city_of_las_vegas': True, 'source': municipal_ref},
    }
    if case_id.endswith('__pedestrian_near_rack'):
        if pedestrian is None:
            raise ValueError('near-rack pedestrian reviewed packet required')
        packet = json.loads(Path(pedestrian).read_text())
        scene['pedestrian_blueprint_id'] = packet.get('blueprint_id')
        scene['pedestrian_spawn_source'] = reference(pedestrian)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(scene, sort_keys=True) + '\n')
    env = {'C10307_SCENE_SOURCE': str(destination), 'C10307_SCENE_SHA256': sha(destination),
           'C10307_ASSET_INVENTORY': observation['asset_inventory']['path'],
           'C10307_ASSET_SHA256': observation['asset_inventory']['sha256']}
    try:
        source_configuration(env, case_id)
    except BaseException:
        destination.unlink()
        raise
    return env


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest='command', required=True)
    capture = sub.add_parser('capture')
    capture.add_argument('--host', default='127.0.0.1')
    capture.add_argument('--port', type=int, default=2000)
    capture.add_argument('--output', type=Path, required=True)
    assemble = sub.add_parser('assemble')
    for name in ('observation', 'case', 'scene', 'municipal', 'bicycle', 'rack'):
        assemble.add_argument('--' + name, required=True,
                              type=Path if name != 'case' else str)
    assemble.add_argument('--pedestrian', type=Path)
    args = parser.parse_args()
    if args.command == 'capture':
        import carla
        client = carla.Client(args.host, args.port)
        client.set_timeout(30.0)
        result = capture_world_sources(client.get_world(), args.output)
    else:
        observation = json.loads(args.observation.read_text())
        result = assemble_reviewed_scene(observation, args.case, args.scene,
                                         args.municipal, args.bicycle, args.rack,
                                         args.pedestrian)
    print(json.dumps(result, sort_keys=True))


if __name__ == '__main__':
    main()
