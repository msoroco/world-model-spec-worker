"""Source-bound CPU semantic sidecar for the authored center turn lane.

The sidecar does not alter Core output. It makes the missing Core structure
explicit while retaining a checkable polygon and lane-use provenance.
"""
import hashlib
import importlib.util
import json
from pathlib import Path
import xml.etree.ElementTree as ET

from shapely.geometry import Point, Polygon

HERE = Path(__file__).resolve().parent


def sha(data):
    return hashlib.sha256(data).hexdigest()


def source_region(xodr):
    root = ET.fromstring(xodr)
    road = root.find("./road[@id='1']")
    if road is None:
        raise ValueError('Source center-lane road absent')
    geometry = road.find('./planView/geometry')
    if geometry is None or geometry.find('line') is None:
        raise ValueError('Center-lane geometry is not the authored straight segment')
    if abs(float(geometry.attrib['hdg'])) > 1e-9:
        raise ValueError('Center-lane road heading changed')
    sections = road.findall('./lanes/laneSection')
    if len(sections) != 1 or float(sections[0].attrib['s']) != 0:
        raise ValueError('Center-lane section changed')
    lane = sections[0].find("./right/lane[@id='-1']")
    if lane is None or lane.attrib.get('type') != 'bidirectional':
        raise ValueError('Bidirectional center lane absent')
    use = lane.find("userData[@code='lane_use']")
    if use is None or use.attrib.get('value') != 'left_turn_only_both_directions':
        raise ValueError('Turn-only bidirectional lane designation absent')
    width = lane.findall('width')
    if len(width) != 1 or any(abs(float(width[0].attrib.get(k, 0))) > 1e-9 for k in ('sOffset', 'b', 'c', 'd')):
        raise ValueError('Center-lane width profile changed')
    lane_width = float(width[0].attrib['a'])
    if lane_width <= 0:
        raise ValueError('Center-lane width invalid')
    offsets = road.findall('./lanes/laneOffset')
    if len(offsets) != 1 or any(abs(float(offsets[0].attrib.get(k, 0))) > 1e-9 for k in ('s', 'a', 'b', 'c', 'd')):
        raise ValueError('Center-lane offset changed')
    x0, y0, length = (float(geometry.attrib[key]) for key in ('x', 'y', 'length'))
    if abs(length-float(road.attrib['length'])) > 1e-9:
        raise ValueError('Center-lane road length changed')
    polygon = Polygon(((x0, y0), (x0+length, y0),
                       (x0+length, y0-lane_width), (x0, y0-lane_width)))
    if not polygon.is_valid or polygon.area <= 0 or not polygon.covers(Point(-40, 0)):
        raise ValueError('Center lane does not cover the surveyed point')
    return {'road_id': 1, 'lane_section': 0, 'lane_id': -1,
            'native_lane_type': 'bidirectional',
            'authored_use': use.attrib['value'],
            'boundary': [[float(x), float(y)] for x, y in list(polygon.exterior.coords)[:-1]],
            'area_m2': round(polygon.area, 6), 'source_xodr_sha256': sha(xodr.encode())}


def check_converted(region, converted):
    scenes = converted.get('scenes', [])
    if not scenes:
        raise ValueError('Converted Core scenes absent')
    point = Point(-40, 0)
    present = [any(row.get('kind') == 'lane' and
                   Polygon(row['boundary']).covers(point)
                   for row in scene['structures']) for scene in scenes]
    return {'core_scene_count': len(scenes),
            'core_center_lane_region_present_in_all_scenes': all(present),
            'core_center_lane_region_present_in_any_scene': any(present),
            'source_sidecar_region': region,
            'source_semantics_checked': True,
            'core_semantics_passed': all(present)}


def main():
    spec = importlib.util.spec_from_file_location('authored_geometry', HERE/'native/geometry.py')
    geometry = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(geometry)
    source = geometry.open_drive()
    region = source_region(source)
    log = (HERE/'package-compatibility-below_50_ft-primary.log').read_text().splitlines()
    if not log or not log[0].startswith('scratch '):
        raise ValueError('Exact Core package log absent')
    converted_path = Path(log[0][8:])/'output/converted/trace.json'
    converted_bytes = converted_path.read_bytes()
    result = check_converted(region, json.loads(converted_bytes))
    result['converted_trace_sha256'] = sha(converted_bytes)
    result['scope'] = 'authored source sidecar and exact synthetic Core output; no Native or physical proof'
    print(json.dumps(result, sort_keys=True))


if __name__ == '__main__':
    main()
