"""Authored C158190 junction and strict Native readback for the yield branch.

XML checks establish only the authored design. The Native checks must run after
CARLA loads it; map geometry, a proper sign face, and missing markings still
need retained source-camera and map evidence.
"""
import hashlib
import json
import math
import xml.etree.ElementTree as ET
from pathlib import Path

ROAD = Path(__file__).resolve().parent / 'native-map-plan/yield-nearest-view.xodr'
JUNCTION = 158191
APPROACH = 158190
THROUGH = (158194, 158195, 158196)


def opendrive_to_carla(x, y):
    """CARLA's Native world reflects the OpenDRIVE map's Y axis."""
    return (float(x), -float(y))


def _lanes(road):
    section = road.find('./lanes/laneSection')
    if section is None:
        raise ValueError('Missing authored lane section')
    return {int(lane.attrib['id']): lane for lane in section.findall('./left/lane')
            + section.findall('./right/lane') if lane.attrib.get('type') == 'driving'}


def validate_authored_site(path=ROAD):
    path = Path(path)
    document = ET.parse(path).getroot()
    if document.tag != 'OpenDRIVE':
        raise ValueError('Not an OpenDRIVE site')
    roads = {int(road.attrib['id']): road for road in document.findall('road')}
    if set(roads) != {158190, 158192, 158193, *THROUGH}:
        raise ValueError('Authored junction road inventory differs')
    if set(_lanes(roads[APPROACH])) != {-1}:
        raise ValueError('Yield approach is not one-way')
    if any(set(_lanes(roads[rid])) != {-1, 1} for rid in THROUGH):
        raise ValueError('Through highway is not two-way')
    if any(road.attrib.get('junction') != str(JUNCTION) for road in
           (roads[158192], roads[158195])):
        raise ValueError('Crossing segments lack junction membership')
    for rid, x, y, hdg, length in ((APPROACH, -80, 0, 0, 72),
                                   (158192, -8, 0, 0, 16),
                                   (158193, 8, 0, 0, 72),
                                   (158194, 0, -80, math.pi / 2, 72),
                                   (158195, 0, -8, math.pi / 2, 16),
                                   (158196, 0, 8, math.pi / 2, 72)):
        geometry = roads[rid].find('./planView/geometry')
        if geometry is None or geometry.find('line') is None or any(
                not math.isclose(float(geometry.attrib[key]), value, abs_tol=1e-9)
                for key, value in (('x', x), ('y', y), ('hdg', hdg), ('length', length))):
            raise ValueError('Authored road centerline differs')
    junction = document.find(f"./junction[@id='{JUNCTION}']")
    if junction is None:
        raise ValueError('Missing authored junction')
    links = {(int(c.attrib['incomingRoad']), int(c.attrib['connectingRoad']),
              c.attrib['contactPoint'], tuple((int(link.attrib['from']), int(link.attrib['to']))
              for link in c.findall('laneLink'))) for c in junction.findall('connection')}
    if links != {(APPROACH, 158192, 'start', ((-1, -1),)),
                 (158194, 158195, 'start', ((-1, -1),)),
                 (158196, 158195, 'end', ((1, 1),))}:
        raise ValueError('One-way/through junction lane connections differ')
    signals = roads[APPROACH].findall('./signals/signal')
    if len(signals) != 1:
        raise ValueError('Expected one authored yield sign')
    sign = signals[0]
    validity = sign.find('validity')
    if (sign.attrib.get('type') != '205' or sign.attrib.get('orientation') != '+'
            or not math.isclose(float(sign.attrib['s']), 60)
            or validity is None or (validity.attrib.get('fromLane'),
                                    validity.attrib.get('toLane')) != ('-1', '-1')):
        raise ValueError('Yield sign does not govern the selected approach lane')
    if document.findall('.//object') or len(document.findall('.//signal')) != 1:
        raise ValueError('Authored markings or other controls are present')
    return {'format': 'worker-c158190-authored-yield-site',
            'road_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
            'approach_road_id': APPROACH, 'approach_lane_id': -1,
            'through_road_ids': list(THROUGH), 'junction_id': JUNCTION,
            'yield_signal_id': sign.attrib['id'],
            'no_authored_stop_line_or_crosswalk_objects': True,
            'native_marking_absence_claimed': False}


def validate_native_site(world, *, location_factory=None):
    """Reject a loaded map that lacks the intended lanes or sign trigger."""
    if location_factory is None:
        import carla
        location_factory = carla.Location
    road_map = world.get_map()
    expected = ((-20, -1.8, APPROACH, -1, False),
                (0, -1.8, 158192, -1, True),
                (1.8, -20, 158194, -1, False),
                (1.8, 0, 158195, -1, True),
                (-1.8, 20, 158196, 1, False))
    for map_x, map_y, road_id, lane_id, is_junction in expected:
        x, y = opendrive_to_carla(map_x, map_y)
        point = location_factory(x=x, y=y, z=.25)
        waypoint = road_map.get_waypoint(point, project_to_road=False)
        if (waypoint is None or waypoint.road_id != road_id
                or waypoint.lane_id != lane_id
                or bool(waypoint.is_junction) != is_junction):
            raise ValueError(f'Native road/lane/junction readback differs at {(x, y)}')
    approach_x, approach_y = opendrive_to_carla(-20, -1.8)
    approach_point = location_factory(x=approach_x, y=approach_y, z=.25)
    signs = [actor for actor in world.get_actors().filter('traffic.yield*')
             if actor.trigger_volume.contains(approach_point, actor.get_transform())]
    if len(signs) != 1:
        raise ValueError(f'Expected one Native yield trigger governing approach; found {len(signs)}')
    return {'native_map_name': road_map.name, 'native_yield_sign_id': signs[0].id,
            'native_approach_road_id': APPROACH, 'native_through_road_ids': list(THROUGH),
            'native_marking_absence_claimed': False,
            'properly_erected_sign_face_claimed': False}


def load_native_site(client):
    """Explicit Native operation; never called by CPU diagnostics."""
    validate_authored_site()
    world = client.generate_opendrive_world(ROAD.read_text())
    return world, validate_native_site(world)


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--receipt', type=Path, required=True)
    args = parser.parse_args()
    report = validate_authored_site()
    report['script_sha256'] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    report['native_readback_pending'] = True
    args.receipt.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({'authored_site_valid': True, 'native_readback_pending': True,
                      'road_sha256': report['road_sha256']}))
