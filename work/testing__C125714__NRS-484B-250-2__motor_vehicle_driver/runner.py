"""C125714 exact-case Native entrypoint; --check is a CPU-only preflight."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import xml.etree.ElementTree as ET
from pathlib import Path

from native_crossing import CASE_SUFFIXES, points


def require(ok, message):
    if not ok:
        raise ValueError(message)


def check_scene(scene_path=Path('scene.json')):
    scene_path = Path(scene_path).resolve()
    scene = json.loads(scene_path.read_text(encoding='utf-8'))
    base = 'testing__C125714__NRS-484B-250-2__motor_vehicle_driver'
    require(scene.get('case_id') in {base + '__' + s for s in CASE_SUFFIXES},
            'wrong exact C125714 case')
    require(scene.get('cell_id') == 'C125714' and
            scene.get('law_id') == 'NRS-484B-250-2' and
            scene.get('actor') == 'motor_vehicle_driver', 'wrong law/cell/actor')
    require(scene.get('source_kind') == 'worker engineering candidate; Native and legal review pending',
            'engineering candidate provenance changed')
    road = scene_path.parent / scene.get('map_source', '')
    require(road.is_file() and not road.is_symlink() and
            hashlib.sha256(road.read_bytes()).hexdigest() == scene.get('map_source_sha256'),
            'candidate OpenDRIVE missing or changed')
    root = ET.fromstring(road.read_bytes())
    require(root.tag == 'OpenDRIVE', 'invalid OpenDRIVE root')
    roads = {r.get('id'): r for r in root.findall('road')}
    require({'10', '31', '110', '131'} <= set(roads) and
            roads['10'].find('link/successor').get('elementType') == 'junction' and
            roads['31'].find('link/successor').get('elementType') == 'junction',
            'two approach roads do not reach authored junction')
    junction = root.find("junction[@id='1']")
    require(junction is not None and {'10', '31'} <=
            {x.get('incomingRoad') for x in junction.findall('connection')},
            'authored crossing lacks both junction connections')
    require(scene.get('ego_highway') != scene.get('other_highway') and
            scene.get('ego_side') == 'left' and scene.get('other_side') == 'right' and
            scene.get('approach_relation') == 'crossing',
            'different-highway left/right crossing missing')
    for name in ('ego', 'other'):
        points(scene.get(name + '_route_xyz_m'), name)
    require(scene['ego_route_xyz_m'][0][0] < -10 and
            scene['ego_route_xyz_m'][-1][0] > 10 and
            scene['other_route_xyz_m'][0][1] < -10 and
            scene['other_route_xyz_m'][-1][1] > 10,
            'authored routes do not cross at median opening')
    require(scene.get('capture_rate_hz') == 20 and
            type(scene.get('duration_s')) in (int, float) and scene['duration_s'] >= 8 and
            type(scene.get('requested_entry_offset_s')) in (int, float) and
            math.isfinite(scene['requested_entry_offset_s']),
            '20 Hz capture or timing request invalid')
    cameras = scene.get('cameras')
    profile = [('overview', 1920, 1080), ('approach', 1280, 720),
               ('reference_corner', 1280, 720), ('driver_reference', 1280, 720)]
    require(isinstance(cameras, list) and len(cameras) == 4 and
            [(c.get('name'), c.get('width'), c.get('height')) for c in cameras] == profile and
            all(c.get('pose_strategy') and c.get('fov_deg') for c in cameras),
            'four-camera capture profile differs')
    return scene, road


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--scene', default='scene.json')
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--output-dir')
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=2000)
    args = parser.parse_args()
    scene, road = check_scene(Path(args.scene))
    if args.check:
        print(json.dumps({'case_id': scene['case_id'],
                          'static_construction_valid': True,
                          'native_started': False,
                          'candidate_map_sha256': scene['map_source_sha256']}))
    elif args.output_dir:
        from native_capture import run_native
        run_native(scene, road, Path(args.output_dir), args.host, args.port)
    else:
        parser.error('use --check or --output-dir')


if __name__ == '__main__':
    main()
