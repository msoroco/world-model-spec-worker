"""Build isolated one-direction-per-road divided-highway CPU candidates."""
import copy
import hashlib
import json
import xml.etree.ElementTree as ET
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
DEST = HERE / 'split-divided-experiment'
CASES = ('divided_reference', 'divided_opening')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')


def split_road(source):
    root = ET.fromstring(source)
    roads = {int(item.attrib['id']): item for item in root.findall('road')}
    if set(roads) != {503, 504, 505}:
        raise ValueError('Unexpected divided highway segments')
    for original_id in (503, 504, 505):
        original = roads[original_id]
        reverse = copy.deepcopy(original)
        reverse.attrib['id'] = str(original_id + 3)
        reverse.attrib['name'] += '-westbound'
        forward_lanes = original.find('./lanes/laneSection')
        reverse_lanes = reverse.find('./lanes/laneSection')
        if len(forward_lanes.findall('./left/lane')) != 4 or len(forward_lanes.findall('./right/lane')) != 3:
            raise ValueError('Expected divided highway lane count')
        forward_lanes.find('left').clear()
        reverse_lanes.find('right').clear()
        reverse_link = reverse.find('link')
        reverse_link.clear()
        if original_id > 503:
            ET.SubElement(reverse_link, 'predecessor', elementType='road',
                          elementId=str(original_id + 2), contactPoint='end')
        if original_id < 505:
            ET.SubElement(reverse_link, 'successor', elementType='road',
                          elementId=str(original_id + 4), contactPoint='start')
        root.append(reverse)
    return ET.tostring(root, encoding='unicode') + '\n'


OVERRIDE = '''
_bidirectional_divided_road = road
def road():
    import copy
    import xml.etree.ElementTree as ET
    root = ET.fromstring(_bidirectional_divided_road())
    roads = {int(item.attrib['id']): item for item in root.findall('road')}
    for original_id in (503, 504, 505):
        original = roads[original_id]
        reverse = copy.deepcopy(original)
        reverse.attrib['id'] = str(original_id + 3)
        reverse.attrib['name'] += '-westbound'
        original.find('./lanes/laneSection/left').clear()
        reverse.find('./lanes/laneSection/right').clear()
        link = reverse.find('link')
        link.clear()
        if original_id > 503:
            ET.SubElement(link, 'predecessor', elementType='road',
                          elementId=str(original_id + 2), contactPoint='end')
        if original_id < 505:
            ET.SubElement(link, 'successor', elementType='road',
                          elementId=str(original_id + 4), contactPoint='start')
        root.append(reverse)
    return ET.tostring(root, encoding='unicode') + '\\n'

'''


def main():
    original_manifest = json.loads((HERE / 'execution-manifest.json').read_text())
    manifest = copy.deepcopy(original_manifest)
    manifest['cases'] = [copy.deepcopy(entry) for entry in original_manifest['cases']
                         if entry['case_id'].rsplit('__', 1)[-1] in CASES]
    manifest['runtime_manifest_sha256'] = sha(ROOT / 'runtime/pipeline/SOURCE-MANIFEST.json')
    manifest['status'] = 'isolated_split_divided_primary_probe'
    DEST.mkdir(exist_ok=True)
    common_road = None
    for entry in manifest['cases']:
        suffix = entry['case_id'].rsplit('__', 1)[-1]
        source = json.loads((HERE / entry['construction']).read_text())
        original_road = next(item['content'] for item in source['files'] if item['path'] == 'road.xodr')
        road = split_road(original_road)
        if common_road is None:
            common_road = road
        elif road != common_road:
            raise ValueError('Selected divided cases use different maps')
        road_sha = hashlib.sha256(road.encode()).hexdigest()
        for item in source['files']:
            path = item['path']
            if path.endswith('.xodr'):
                item['content'] = road
            elif path.endswith('config.json'):
                cfg = json.loads(item['content'])
                if 'road_sha256' in cfg:
                    cfg['road_sha256'] = road_sha
                item['content'] = json.dumps(cfg, indent=2, sort_keys=True) + '\n'
            elif path.endswith('/native/divided_opening.py'):
                content = item['content']
                marker = '\n\nif __name__ == "__main__":'
                if content.count(marker) != 1:
                    raise ValueError('Divided generator entrypoint changed')
                content = content.replace(marker, '\n' + OVERRIDE + marker)
                content = content.replace('if set(pieces) != {503, 504, 505}:',
                                          'if set(pieces) != {503, 504, 505, 506, 507, 508}:')
                content = content.replace('pieces[ident].findall("./lanes/laneSection/left/lane")',
                                          'pieces[ident+3].findall("./lanes/laneSection/left/lane")')
                item['content'] = content
            elif path.endswith('/native/capture_divided.py'):
                item['content'] = item['content'].replace('("reference_westbound", 503,',
                                                        '("reference_westbound", 506,').replace(
                                                        '("reference_median", 503,',
                                                        '("reference_median", 506,').replace(
                                                        '("opening_crossing", 504,',
                                                        '("opening_crossing", 507,').replace(
                                                        '("opening_westbound", 504,',
                                                        '("opening_westbound", 507,').replace(
                                                        '("departure_median", 505,',
                                                        '("departure_median", 508,')
            elif path.endswith('/native/process_original_divided.py'):
                item['content'] = item['content'].replace('"reference_westbound": (503,',
                                                        '"reference_westbound": (506,').replace(
                                                        '"reference_median": (503,',
                                                        '"reference_median": (506,').replace(
                                                        '"opening_crossing": (504,',
                                                        '"opening_crossing": (507,').replace(
                                                        '"opening_westbound": (504,',
                                                        '"opening_westbound": (507,').replace(
                                                        '"departure_median": (505,',
                                                        '"departure_median": (508,').replace(
                                                        'not in (503, 504, 505, None)',
                                                        'not in (503, 504, 505, 506, 507, 508, None)')
            elif path == 'tests/test_divided.py':
                old = "self.assertEqual(xml.count('<road id='),3)"
                if item['content'].count(old) != 1:
                    raise ValueError('Divided topology test changed')
                item['content'] = item['content'].replace(old,
                    "self.assertEqual(xml.count('<road id='),6)")
        construction_path = DEST / (suffix + '-construction.json')
        write(construction_path, source)
        entry['construction'] = str(construction_path.relative_to(HERE))
        entry['construction_sha256'] = sha(construction_path)
        entry['candidates'] = []
        entry.pop('fixture_recipe', None)
        entry['preparation_status'] = 'isolated split carriageway CPU probe; unselected'
    manifest_path = HERE / 'split-divided-experiment-manifest.json'
    write(manifest_path, manifest)
    print(json.dumps({'road_sha256': hashlib.sha256(common_road.encode()).hexdigest(),
                      'manifest_sha256': sha(manifest_path)}))


if __name__ == '__main__':
    main()
