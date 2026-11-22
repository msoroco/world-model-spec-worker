"""Build an isolated source-geometry probe for the selected U-turn reference.

The local road section at the maneuver is a temporary non-driving shoulder
on the opposing side, so Native topology does not invent a continuous centre
divider through the crossover. This probe does not change selected delivery.
"""
import copy
import hashlib
import io
import json
import xml.etree.ElementTree as ET
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOURCE = HERE / 'execution-manifest.json'
DEST = HERE / 'centerline-gap-experiment'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def road_with_gap(source):
    tree = ET.parse(io.StringIO(source))
    road = next(r for r in tree.getroot().findall('road') if r.attrib['id'] == '403')
    lanes = road.find('lanes')
    sections = lanes.findall('laneSection')
    if len(sections) != 1 or sections[0].attrib['s'] != '0':
        raise ValueError('Expected one original section on road 403')
    original = sections[0]
    shoulder = copy.deepcopy(original)
    shoulder.attrib['s'] = '50'
    for lane in shoulder.findall("./left/lane[@type='driving']"):
        lane.attrib['type'] = 'shoulder'
    restored = copy.deepcopy(original)
    restored.attrib['s'] = '75'
    lanes.extend((shoulder, restored))
    return ET.tostring(tree.getroot(), encoding='unicode') + '\n'


def build():
    manifest = json.loads(SOURCE.read_text())
    entry = copy.deepcopy(next(e for e in manifest['cases'] if e['case_id'].endswith('__reference')))
    construction = json.loads((HERE / entry['construction']).read_text())
    road_files = [f for f in construction['files'] if f['path'].endswith('.xodr')]
    original = road_files[0]['content']
    if any(f['content'] != original for f in road_files):
        raise ValueError('Original road copies differ')
    changed = road_with_gap(original)
    for file in road_files:
        file['content'] = changed
    road_hash = hashlib.sha256(changed.encode()).hexdigest()
    for file in construction['files']:
        if file['path'].endswith('config.json'):
            config = json.loads(file['content'])
            config['road_sha256'] = road_hash
            file['content'] = json.dumps(config, indent=2, sort_keys=True) + '\n'
        elif file['path'].endswith('/native/build.py'):
            file['content'] += '''\n\n# Isolated source-topology experiment: no selected delivery mutation.\n_original_road = road\ndef road():\n    import io\n    import xml.etree.ElementTree as ET\n    tree = ET.parse(io.StringIO(_original_road()))\n    road403 = next(r for r in tree.getroot().findall('road') if r.attrib['id'] == '403')\n    lanes = road403.find('lanes')\n    section = lanes.find('laneSection')\n    import copy\n    shoulder = copy.deepcopy(section)\n    shoulder.attrib['s'] = '50'\n    for lane in shoulder.findall("./left/lane[@type='driving']"):\n        lane.attrib['type'] = 'shoulder'\n    restored = copy.deepcopy(section)\n    restored.attrib['s'] = '75'\n    lanes.extend((shoulder, restored))\n    return ET.tostring(tree.getroot(), encoding='unicode') + '\\n'\n'''
        elif file['path'].endswith('/native/check.py'):
            old = "lane.attrib.get('type')!='driving' or"
            if old not in file['content']:
                raise ValueError('Pinned topology check changed')
            file['content'] = file['content'].replace(
                old, "lane.attrib.get('type') not in ('driving','shoulder') or")
    DEST.mkdir(exist_ok=True)
    target = DEST / 'construction.json'
    target.write_text(json.dumps(construction, indent=2, sort_keys=True) + '\n')
    entry['construction'] = str(target.relative_to(HERE))
    entry['construction_sha256'] = sha(target)
    entry['candidates'] = []
    manifest['cases'] = [entry]
    manifest['status'] = 'isolated_work_owned_geometry_probe'
    output = HERE / 'centerline-gap-experiment-manifest.json'
    output.write_text(json.dumps(manifest, indent=2, sort_keys=True) + '\n')
    print(json.dumps({'manifest': output.name, 'sha256': sha(output),
                      'construction_sha256': sha(target)}))


if __name__ == '__main__':
    build()
