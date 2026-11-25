"""Author the no-crosswalk marked-line road variant for selected branch work."""
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET

HERE = Path(__file__).resolve().parent


def build():
    source = HERE / 'native/road.xodr'
    target = HERE / 'native/road_stop_line.xodr'
    tree = ET.parse(source)
    approach = next(road for road in tree.getroot().findall('road')
                    if road.get('id') == '1')
    objects = approach.find('objects')
    for item in list(objects):
        if item.get('type') == 'crosswalk':
            objects.remove(item)
    ET.SubElement(objects, 'object', {
        'id': '902', 'name': 'clearly_marked_stop_line', 'type': 'roadMark',
        's': '229', 't': '0', 'zOffset': '0', 'hdg': '0',
        'pitch': '0', 'roll': '0', 'length': '0.4', 'width': '7', 'height': '0'})
    tree.getroot().find('header').set('name', 'C111325-stop-sign-marked-line-no-crosswalk-draft')
    target.write_text(ET.tostring(tree.getroot(), encoding='unicode') + '\n')
    return {'road_sha256': hashlib.sha256(target.read_bytes()).hexdigest(),
            'crosswalk_objects': 0, 'marked_line_objects': 1,
            'physical_rendering_verified': False}


if __name__ == '__main__':
    print(json.dumps(build(), sort_keys=True))
