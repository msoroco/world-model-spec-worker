"""Build an isolated intersection with separate directional connector roads.

The selected construction remains unchanged. This diagnostic preserves both
directions of each crossing street while representing them as distinct roads
inside the junction, where a painted centre divider is not assumed.
"""
import copy
import hashlib
import json
import xml.etree.ElementTree as ET
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
DEST = HERE / 'split-junction-experiment'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def split_road(source):
    root = ET.fromstring(source)
    roads = {int(road.attrib['id']): road for road in root.findall('road')}
    if set(roads) != {403, 404, 405, 406, 407, 408}:
        raise ValueError('Unexpected six-road source intersection')
    junction = next(j for j in root.findall('junction') if j.attrib['id'] == '1')
    for original_id, reverse_id, name in ((404, 409, 'westbound junction connector'),
                                          (407, 410, 'southbound junction connector')):
        original = roads[original_id]
        reverse = copy.deepcopy(original)
        reverse.attrib.update(id=str(reverse_id), name=name)
        original_section = original.find('./lanes/laneSection')
        reverse_section = reverse.find('./lanes/laneSection')
        if len(original_section.findall('./left/lane')) != 3 or len(original_section.findall('./right/lane')) != 3:
            raise ValueError('Expected bidirectional junction road')
        original_section.find('left').clear()
        reverse_section.find('right').clear()
        for section in (original_section, reverse_section):
            mark = section.find('./center/lane/roadMark')
            mark.attrib['type'] = 'none'
        root.insert(list(root).index(junction), reverse)
    for ident, incoming, connecting in ((3, 405, 409), (4, 408, 410)):
        connection = ET.SubElement(junction, 'connection', id=str(ident),
                                   incomingRoad=str(incoming), connectingRoad=str(connecting),
                                   contactPoint='end')
        for lane in (1, 2, 3):
            ET.SubElement(connection, 'laneLink', {'from': str(lane), 'to': str(lane)})
    return ET.tostring(root, encoding='unicode') + '\n'


BUILD_OVERRIDE = '''
_original_bidirectional_road = road
def road():
    import copy
    import xml.etree.ElementTree as ET
    root = ET.fromstring(_original_bidirectional_road())
    roads = {int(item.attrib['id']): item for item in root.findall('road')}
    junction = next(item for item in root.findall('junction') if item.attrib['id'] == '1')
    for original_id, reverse_id, name in ((404, 409, 'westbound junction connector'),
                                          (407, 410, 'southbound junction connector')):
        original = roads[original_id]
        reverse = copy.deepcopy(original)
        reverse.attrib.update(id=str(reverse_id), name=name)
        original_section = original.find('./lanes/laneSection')
        reverse_section = reverse.find('./lanes/laneSection')
        original_section.find('left').clear()
        reverse_section.find('right').clear()
        for section in (original_section, reverse_section):
            section.find('./center/lane/roadMark').attrib['type'] = 'none'
        root.insert(list(root).index(junction), reverse)
    for ident, incoming, connecting in ((3, 405, 409), (4, 408, 410)):
        connection = ET.SubElement(junction, 'connection', id=str(ident),
                                   incomingRoad=str(incoming), connectingRoad=str(connecting),
                                   contactPoint='end')
        for lane in (1, 2, 3):
            ET.SubElement(connection, 'laneLink', {'from': str(lane), 'to': str(lane)})
    return ET.tostring(root, encoding='unicode') + '\\n'
'''

TOPOLOGY_CHECK = '''def topology(path):
    import xml.etree.ElementTree as ET
    root = ET.parse(path).getroot()
    roads = {int(item.attrib['id']): item for item in root.findall('road')}
    if set(roads) != {403, 404, 405, 406, 407, 408, 409, 410}:
        raise ValueError('Split intersection roads changed')
    for ident, road in roads.items():
        section = road.find('./lanes/laneSection')
        left = section.findall('./left/lane')
        right = section.findall('./right/lane')
        if ident in (404, 407):
            expected = (0, 3)
        elif ident in (409, 410):
            expected = (3, 0)
        else:
            expected = (3, 3)
        if (len(left), len(right)) != expected or any(
                lane.attrib.get('type') != 'driving' or
                abs(float(lane.find('width').attrib['a']) - 4) > 1e-8
                for lane in left + right):
            raise ValueError('Directional lane coverage changed')
        if ident in (404, 407, 409, 410) and road.attrib['junction'] != '1':
            raise ValueError('Connector outside intersection')
        if road.find('signals/signal') is not None:
            raise ValueError('Unexpected signal actor')
    connections = {(int(c.attrib['incomingRoad']), int(c.attrib['connectingRoad']))
                   for c in root.find('junction').findall('connection')}
    if connections != {(403, 404), (406, 407), (405, 409), (408, 410)}:
        raise ValueError('Directional junction connections changed')

'''


def write(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')


def main():
    manifest = json.loads((HERE / 'execution-manifest.json').read_text())
    entry = copy.deepcopy(next(e for e in manifest['cases'] if e['case_id'].endswith('__contrast')))
    construction = json.loads((HERE / entry['construction']).read_text())
    road_items = [item for item in construction['files'] if item['path'].endswith('.xodr')]
    originals = {item['content'] for item in road_items}
    if len(originals) != 1:
        raise ValueError('Road copies differ')
    road = split_road(next(iter(originals)))
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
            marker = '\n\ndef pose('
            if item['content'].count(marker) != 1:
                raise ValueError('Native road generator changed')
            item['content'] = item['content'].replace(marker, '\n' + BUILD_OVERRIDE + marker)
        elif path.endswith('/native/check.py'):
            start = item['content'].index('def topology(path):')
            end = item['content'].index('\n\ndef check(bundle):', start)
            item['content'] = item['content'][:start] + TOPOLOGY_CHECK.rstrip() + item['content'][end:]
        elif path.endswith('/native/capture.py'):
            old = "('junction_westbound_outer',404,3,20)"
            if item['content'].count(old) != 1:
                raise ValueError('Native westbound readback changed')
            item['content'] = item['content'].replace(old, "('junction_westbound_outer',409,3,20)")
    DEST.mkdir(exist_ok=True)
    target = DEST / 'construction.json'
    write(target, construction)
    entry['construction'] = str(target.relative_to(HERE))
    entry['construction_sha256'] = sha(target)
    entry['candidates'] = []
    entry.pop('fixture_recipe', None)
    manifest['cases'] = [entry]
    manifest['runtime_manifest_sha256'] = sha(ROOT / 'runtime/pipeline/SOURCE-MANIFEST.json')
    manifest['status'] = 'isolated_split_junction_probe'
    output = HERE / 'split-junction-experiment-manifest.json'
    write(output, manifest)
    print(json.dumps({'road_sha256': road_sha, 'construction_sha256': sha(target),
                      'manifest_sha256': sha(output)}))


if __name__ == '__main__':
    main()
