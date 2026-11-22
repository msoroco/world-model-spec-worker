"""Build a shorter, isolated road-403 U-turn crossover construction.

This is a diagnostic geometry variant. It does not select the construction or
assert that the temporary shoulder is physically or legally acceptable.
"""
import copy
import hashlib
import json
import xml.etree.ElementTree as ET
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
BASE = HERE / 'centerline-gap-experiment'
DEST = HERE / 'localized-crossover-experiment'
START_S = '55'
END_S = '67'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')


def main():
    construction = json.loads((BASE / 'construction.json').read_text())
    for item in construction['files']:
        if not item['path'].endswith('.xodr'):
            continue
        root = ET.fromstring(item['content'])
        road = next(r for r in root.findall('road') if r.attrib['id'] == '403')
        sections = road.find('lanes').findall('laneSection')
        if [section.attrib['s'] for section in sections] != ['0', '50', '75']:
            raise ValueError('Unexpected base crossover geometry')
        sections[1].attrib['s'] = START_S
        sections[2].attrib['s'] = END_S
        item['content'] = ET.tostring(root, encoding='unicode') + '\n'
    roads = {item['content'] for item in construction['files'] if item['path'].endswith('.xodr')}
    if len(roads) != 1:
        raise ValueError('Construction road copies differ')
    road_sha = hashlib.sha256(next(iter(roads)).encode()).hexdigest()
    for item in construction['files']:
        if item['path'].endswith('config.json'):
            config = json.loads(item['content'])
            config['road_sha256'] = road_sha
            item['content'] = json.dumps(config, indent=2, sort_keys=True) + '\n'
        elif item['path'].endswith('/native/build.py'):
            source = item['content']
            for old, new in (("shoulder.attrib['s'] = '50'", f"shoulder.attrib['s'] = '{START_S}'"),
                             ("restored.attrib['s'] = '75'", f"restored.attrib['s'] = '{END_S}'")):
                if source.count(old) != 1:
                    raise ValueError('Pinned native road generator changed')
                source = source.replace(old, new)
            item['content'] = source
    DEST.mkdir(exist_ok=True)
    target = DEST / 'construction.json'
    write(target, construction)
    manifest = copy.deepcopy(json.loads((HERE / 'centerline-gap-experiment-manifest.json').read_text()))
    entry = manifest['cases'][0]
    entry['construction'] = str(target.relative_to(HERE))
    entry['construction_sha256'] = sha(target)
    entry.pop('fixture_recipe', None)
    manifest['runtime_manifest_sha256'] = sha(ROOT / 'runtime/pipeline/SOURCE-MANIFEST.json')
    manifest['status'] = 'isolated_localized_crossover_probe'
    output = HERE / 'localized-crossover-experiment-manifest.json'
    write(output, manifest)
    print(json.dumps({'road_sha256': road_sha, 'construction_sha256': sha(target),
                      'manifest_sha256': sha(output)}))


if __name__ == '__main__':
    main()
