"""Check the authored near-side crosswalk reference against the request."""
import argparse
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET

HERE = Path(__file__).resolve().parent
ROAD = HERE / 'crossroads.xodr'
REQUEST = HERE / 'request-controlled_4.jsonl'


def check(xml_text, requests):
    root = ET.fromstring(xml_text)
    road = next((road for road in root.findall('road') if road.get('id') == '250'), None)
    if road is None:
        raise ValueError('Eastbound approach road absent')
    geometry = road.find('planView/geometry')
    if geometry is None or geometry.find('line') is None or \
            (geometry.get('s'), geometry.get('x'), geometry.get('hdg')) != ('0', '-60', '0'):
        raise ValueError('Approach station-to-x relation differs')
    objects = root.findall('.//object')
    if len(objects) != 1 or objects[0] not in road.findall('objects/object') or \
            objects[0].get('type') != 'crosswalk' or objects[0].get('id') != '751' or \
            (objects[0].get('s'), objects[0].get('length'), objects[0].get('width')) != ('51', '2.0', '3.5'):
        raise ValueError('Near-side crosswalk object geometry differs')
    if any(lane.get('type') == 'sidewalk' for lane in root.findall('.//lane')):
        raise ValueError('Unexpected sidewalk-derived crossing')
    center_x = -60 + float(objects[0].get('s'))
    near_edge_x = center_x - float(objects[0].get('length')) / 2
    if near_edge_x != -10.0 or len(requests) != 600 or any(
            row.get('requested_crosswalk_near_edge_x_m') != near_edge_x or
            row.get('requested_stop_line_present') is not False or
            row.get('requested_near_side_crosswalk_present') is not True
            for row in requests):
        raise ValueError('Crosswalk near-edge request differs from authored object')
    if not any(row['ego_front_x_m'] == near_edge_x for row in requests):
        raise ValueError('Stop plateau at crosswalk near edge absent')
    return {'format': 'c154537-authored-crosswalk-geometry-audit-v1',
            'authored_near_edge_x_m': near_edge_x, 'request_frames': 600,
            'physical_import_or_pixel_claimed': False, 'legal_verdict_claimed': False}


def self_test():
    text = ROAD.read_text()
    rows = [json.loads(line) for line in REQUEST.read_text().splitlines()]
    result = check(text, rows)
    for changed, phrase in ((text.replace('type="crosswalk"', 'type="stopLine"'),
                             'object geometry'),
                            (text.replace('length="2.0"', 'length="3.0"'),
                             'object geometry')):
        try:
            check(changed, rows)
        except ValueError as exc:
            if phrase not in str(exc):
                raise
        else:
            raise AssertionError('Changed authored crossing accepted')
    result['road_sha256'] = hashlib.sha256(ROAD.read_bytes()).hexdigest()
    result['request_sha256'] = hashlib.sha256(REQUEST.read_bytes()).hexdigest()
    result['wrong_type_rejected'] = True
    result['wrong_length_rejected'] = True
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError('Retain prior geometry audit')
    args.output.write_text(json.dumps(self_test(), indent=2) + '\n')
