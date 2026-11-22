"""Isolate a six-driving-lane directional approach without shoulder transitions."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
DEST = HERE / 'directional-approach-experiment'

TRANSFORM = '''def directional_approach(source):
    import copy
    import xml.etree.ElementTree as ET
    root = ET.fromstring(source)
    roads = {int(item.attrib['id']): item for item in root.findall('road')}
    if set(roads) != {403, 404, 405, 406, 407, 408, 409, 410}:
        raise ValueError('Unexpected split junction source')
    east = roads[403]
    sections = east.find('lanes').findall('laneSection')
    if [section.attrib['s'] for section in sections] != ['0', '55', '67']:
        raise ValueError('Unexpected shoulder interval')
    west = copy.deepcopy(east)
    west.attrib.update(id='411', name='east-west westbound approach')
    east_lanes = east.find('lanes')
    west_lanes = west.find('lanes')
    for section in sections[1:]:
        east_lanes.remove(section)
    for section in west_lanes.findall('laneSection')[1:]:
        west_lanes.remove(section)
    east_section = east_lanes.find('laneSection')
    west_section = west_lanes.find('laneSection')
    east_section.find('left').clear()
    west_section.find('right').clear()
    for section in (east_section, west_section):
        section.find('./center/lane/roadMark').attrib['type'] = 'none'
    root.insert(list(root).index(root.find('junction')), west)
    roads[409].find('./link/predecessor').attrib['elementId'] = '411'
    return ET.tostring(root, encoding='unicode') + '\\n'
'''

TOPOLOGY = '''def topology(path):
    import xml.etree.ElementTree as ET
    root = ET.parse(path).getroot()
    roads = {int(item.attrib['id']): item for item in root.findall('road')}
    if set(roads) != {403, 404, 405, 406, 407, 408, 409, 410, 411}:
        raise ValueError('Directional intersection roads changed')
    for ident, road in roads.items():
        sections = road.find('lanes').findall('laneSection')
        if len(sections) != 1 or sections[0].attrib['s'] != '0':
            raise ValueError('Unexpected lane transition')
        section = sections[0]
        left = section.findall('./left/lane')
        right = section.findall('./right/lane')
        if ident in (403, 404, 407):
            expected = (0, 3)
        elif ident in (409, 410, 411):
            expected = (3, 0)
        else:
            expected = (3, 3)
        if (len(left), len(right)) != expected or any(
                lane.attrib.get('type') != 'driving' or
                abs(float(lane.find('width').attrib['a']) - 4) > 1e-8
                for lane in left + right):
            raise ValueError('Six driving lanes not preserved')
        if ident in (404, 407, 409, 410) and road.attrib['junction'] != '1':
            raise ValueError('Connector outside intersection')
    if roads[409].find('./link/predecessor').attrib['elementId'] != '411':
        raise ValueError('Westbound approach link changed')
    connections = {(int(c.attrib['incomingRoad']), int(c.attrib['connectingRoad']))
                   for c in root.find('junction').findall('connection')}
    if connections != {(403, 404), (406, 407), (405, 409), (408, 410)}:
        raise ValueError('Directional junction connections changed')

'''


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')


def main():
    scope = {}
    exec(TRANSFORM, scope)
    transform = scope['directional_approach']
    manifest = json.loads((HERE / 'current-16-manifest-reference-primary.json').read_text())
    entry = manifest['cases'][0]
    original = json.loads((HERE / entry['construction']).read_text())
    road = next(item['content'] for item in original['files'] if item['path'] == 'road.xodr')
    changed = transform(road)
    road_sha = hashlib.sha256(changed.encode()).hexdigest()
    for item in original['files']:
        path = item['path']
        if path.endswith('.xodr'):
            item['content'] = changed
        elif path.endswith('config.json'):
            config = json.loads(item['content'])
            if 'road_sha256' in config:
                config['road_sha256'] = road_sha
            item['content'] = json.dumps(config, indent=2, sort_keys=True) + '\n'
        elif path.endswith('/native/build.py'):
            item['content'] += ('\n_directional_source_road = road\n' + TRANSFORM +
                                '\ndef road():\n    return directional_approach(_directional_source_road())\n')
        elif path.endswith('/native/check.py'):
            start = item['content'].index('def topology(path):')
            end = item['content'].index('\ndef check(bundle):', start)
            item['content'] = item['content'][:start] + TOPOLOGY + item['content'][end:]
        elif path.endswith('/native/capture.py'):
            item['content'] = item['content'].replace(
                "('west_westbound_outer',403,3,20)",
                "('west_westbound_outer',411,3,20)")
        elif path.endswith('/native/process_original.py'):
            item['content'] = item['content'].replace(
                '"west_westbound_outer": (403, 3)',
                '"west_westbound_outer": (411, 3)')
            item['content'] = item['content'].replace(
                'not in (403, 404, 405, None)',
                'not in (403, 404, 405, 411, None)')
    target = DEST / 'construction.json'
    write(target, original)
    entry['construction'] = str(target.relative_to(HERE))
    entry['construction_sha256'] = sha(target)
    entry['candidates'] = []
    entry['preparation_status'] = 'isolated directional approach CPU probe'
    manifest['status'] = 'isolated_directional_approach_probe'
    output = HERE / 'directional-approach-experiment-manifest.json'
    write(output, manifest)
    print(json.dumps({'road_sha256': road_sha, 'construction_sha256': sha(target),
                      'manifest_sha256': sha(output)}))


if __name__ == '__main__':
    main()
