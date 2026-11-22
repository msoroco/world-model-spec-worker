"""Combine the directional crossing and a 12 m west approach opening.

This remains an isolated CPU experiment and does not select a delivery map.
"""
import copy
import hashlib
import json
import xml.etree.ElementTree as ET
from pathlib import Path
from probe_split_junction import BUILD_OVERRIDE as SPLIT_BUILD_OVERRIDE
from probe_split_junction import TOPOLOGY_CHECK

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
DEST = HERE / 'shared-junction-experiment'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')


def open_approach(source):
    root = ET.fromstring(source)
    road = next(r for r in root.findall('road') if r.attrib['id'] == '403')
    lanes = road.find('lanes')
    section = lanes.find('laneSection')
    if len(lanes.findall('laneSection')) != 1:
        raise ValueError('Unexpected original approach sections')
    shoulder = copy.deepcopy(section)
    shoulder.attrib['s'] = '55'
    for lane in shoulder.findall('./left/lane'):
        if lane.attrib['type'] != 'driving':
            raise ValueError('Unexpected opposing lane')
        lane.attrib['type'] = 'shoulder'
    restored = copy.deepcopy(section)
    restored.attrib['s'] = '67'
    lanes.extend((shoulder, restored))
    return ET.tostring(root, encoding='unicode') + '\n'


BUILD_OVERRIDE = '''
# Isolated approach opening layered over directional junction connectors.
_directional_junction_road = road
def road():
    import copy
    import xml.etree.ElementTree as ET
    root = ET.fromstring(_directional_junction_road())
    approach = next(item for item in root.findall('road') if item.attrib['id'] == '403')
    lanes = approach.find('lanes')
    section = lanes.find('laneSection')
    shoulder = copy.deepcopy(section)
    shoulder.attrib['s'] = '55'
    for lane in shoulder.findall('./left/lane'):
        lane.attrib['type'] = 'shoulder'
    restored = copy.deepcopy(section)
    restored.attrib['s'] = '67'
    lanes.extend((shoulder, restored))
    return ET.tostring(root, encoding='unicode') + '\\n'
'''


def main():
    construction = json.loads((HERE / 'split-junction-experiment/construction.json').read_text())
    road_items = [item for item in construction['files'] if item['path'].endswith('.xodr')]
    sources = {item['content'] for item in road_items}
    if len(sources) != 1:
        raise ValueError('Road copies differ')
    road = open_approach(next(iter(sources)))
    road_sha = hashlib.sha256(road.encode()).hexdigest()
    for item in construction['files']:
        path = item['path']
        if path.endswith('.xodr'):
            item['content'] = road
        elif path.endswith('config.json'):
            config = json.loads(item['content'])
            config['road_sha256'] = road_sha
            item['content'] = json.dumps(config, indent=2, sort_keys=True) + '\n'
        elif path.endswith('/native/build.py'):
            item['content'] += '\n' + BUILD_OVERRIDE
        elif path.endswith('/native/check.py'):
            old = "    connections = {(int(c.attrib['incomingRoad']), int(c.attrib['connectingRoad']))"
            if item['content'].count(old) != 1:
                raise ValueError('Native topology check changed')
            extra = '''    approach_sections = roads[403].find('lanes').findall('laneSection')
    if [section.attrib['s'] for section in approach_sections] != ['0', '55', '67']:
        raise ValueError('Approach opening changed')
    if any(lane.attrib['type'] != 'shoulder'
           for lane in approach_sections[1].findall('./left/lane')):
        raise ValueError('Opposing approach lanes not open')
'''
            item['content'] = item['content'].replace(old, extra + old)
    DEST.mkdir(exist_ok=True)
    target = DEST / 'construction.json'
    write(target, construction)
    contrast_manifest = json.loads((HERE / 'split-junction-experiment-manifest.json').read_text())
    reference_manifest = json.loads((HERE / 'localized-crossover-experiment-manifest.json').read_text())
    contrast = copy.deepcopy(contrast_manifest['cases'][0])
    reference = copy.deepcopy(reference_manifest['cases'][0])
    for entry in (contrast, reference):
        entry['construction'] = str(target.relative_to(HERE))
        entry['construction_sha256'] = sha(target)
        entry['candidates'] = []
        entry['preparation_status'] = 'isolated shared-map CPU probe; unselected'
    reference_construction = json.loads((HERE / 'localized-crossover-experiment/construction.json').read_text())
    for item in reference_construction['files']:
        path = item['path']
        if path.endswith('.xodr'):
            item['content'] = road
        elif path.endswith('config.json'):
            config = json.loads(item['content'])
            config['road_sha256'] = road_sha
            item['content'] = json.dumps(config, indent=2, sort_keys=True) + '\n'
        elif path.endswith('/native/build.py'):
            item['content'] += '\n' + SPLIT_BUILD_OVERRIDE
        elif path.endswith('/native/check.py'):
            start = item['content'].index('def topology(path):')
            end = item['content'].index('\n\ndef check(bundle):', start)
            item['content'] = item['content'][:start] + TOPOLOGY_CHECK.rstrip() + item['content'][end:]
            old = "    connections = {(int(c.attrib['incomingRoad']), int(c.attrib['connectingRoad']))"
            extra = '''    approach_sections = roads[403].find('lanes').findall('laneSection')
    if [section.attrib['s'] for section in approach_sections] != ['0', '55', '67']:
        raise ValueError('Approach opening changed')
    if any(lane.attrib['type'] != 'shoulder'
           for lane in approach_sections[1].findall('./left/lane')):
        raise ValueError('Opposing approach lanes not open')
'''
            item['content'] = item['content'].replace(old, extra + old)
        elif path.endswith('/native/capture.py'):
            old = "('junction_westbound_outer',404,3,20)"
            if item['content'].count(old) != 1:
                raise ValueError('Native westbound readback changed')
            item['content'] = item['content'].replace(old, "('junction_westbound_outer',409,3,20)")
    reference_target = DEST / 'construction-reference.json'
    write(reference_target, reference_construction)
    reference['construction'] = str(reference_target.relative_to(HERE))
    reference['construction_sha256'] = sha(reference_target)
    output = copy.deepcopy(contrast_manifest)
    output['cases'] = [reference, contrast]
    output['runtime_manifest_sha256'] = sha(ROOT / 'runtime/pipeline/SOURCE-MANIFEST.json')
    output['status'] = 'isolated_shared_junction_probe'
    manifest_path = HERE / 'shared-junction-experiment-manifest.json'
    write(manifest_path, output)
    print(json.dumps({'road_sha256': road_sha, 'construction_sha256': sha(target),
                      'manifest_sha256': sha(manifest_path)}))


if __name__ == '__main__':
    main()
