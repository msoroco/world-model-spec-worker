"""Retain the generated Native OpenDRIVE map in all selected curb candidates."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
OLD = '        native_map_sha = hashlib.sha256(world.get_map().to_opendrive().encode()).hexdigest()'
NEW = '''        native_road_text = world.get_map().to_opendrive()
        native_map_sha = hashlib.sha256(native_road_text.encode()).hexdigest()
        with (output / 'native-road.xodr').open('x') as native_road_file:
            native_road_file.write(native_road_text)'''


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    manifest_path = HERE / 'v2-primary-manifest.json'
    manifest = json.loads(manifest_path.read_text())
    patched = []
    for entry in manifest['cases']:
        for variant in [entry] + entry['candidates']:
            path = HERE / variant['construction']
            construction = json.loads(path.read_text())
            runner = next(item for item in construction['files'] if item['path'] == 'runner.py')
            content = runner['content']
            if content.count(OLD) != 1:
                if NEW not in content:
                    raise ValueError('Unexpected Native map source: ' + str(path))
            else:
                content = content.replace(OLD, NEW)
            context = "            'native_road_sha256': native_map_sha,"
            if content.count(context) != 1:
                raise ValueError('Native curb context source differs: ' + str(path))
            if "'native_road_source': 'native-road.xodr'" not in content:
                content = content.replace(context, context + "\n            'native_road_source': 'native-road.xodr',")
            runner['content'] = content
            path.write_text(json.dumps(construction, indent=2) + '\n')
            variant['construction_sha256'] = sha(path)
            patched.append((entry['case_id'], variant.get('id', 'primary'), variant['construction_sha256']))
            if entry['case_id'].endswith('__probe_1') and variant is entry:
                (HERE / 'runner.py').write_text(content)
    if len(patched) != 4:
        raise ValueError('Four selected primary/fallback constructions required')
    manifest_path.write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps({'patched_constructions': patched, 'manifest_sha256': sha(manifest_path)}))


if __name__ == '__main__':
    main()
