"""Freeze selected source bundles with one truthful four-view camera contract."""
import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
CAMERA_FOV = {'overview': 80, 'approach': 110,
              'reference_corner': 105, 'driver_reference': 105}


def dump(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def stabilize(case, candidate):
    source = HERE / 'current-candidates' / case / candidate / 'construction.json'
    data = json.loads(source.read_text())
    data['status'] = 'selected_cpu_preparation'
    for item in data['files']:
        if item['path'] == 'config.json':
            config = json.loads(item['content'])
            config['status'] = 'selected_cpu_preparation'
            for camera in config['cameras']:
                camera['fov_deg'] = CAMERA_FOV[camera['name']]
            item['content'] = json.dumps(config, indent=2, ensure_ascii=False) + '\n'
        if item['path'] == 'tests/test_constructions.py':
            item['content'] = item['content'].replace("r['camera_plan'][1]['fov_deg']) for r in rows", "r['camera_plan'][1]['fov_deg'], tuple(r['camera_plan'][1]['xyz_m'])) for r in rows")
        if item['path'] == 'cameras.py':
            item['content'] = item['content'].replace("'fov_deg':110 if wide else 90", "'fov_deg':110")
    path = HERE / 'selected-candidates' / case / candidate / 'construction.json'
    dump(path, data)
    return path, data


manifest = copy.deepcopy(json.loads((HERE / 'current-diagnostic-manifest.json').read_text()))
manifest['format'] = 'worker-execution-manifest'
manifest['status'] = 'selected_cpu_preparation'
for entry in manifest['cases']:
    case = entry['case_id'].rsplit('__', 1)[-1]
    path, data = stabilize(case, 'primary')
    entry['construction'] = path.relative_to(HERE).as_posix()
    entry['construction_sha256'] = sha(path)
    entry['candidates'] = [x for x in entry['candidates'] if x['id'] in ('fallback1', 'fallback3')]
    for candidate in entry['candidates']:
        path, _ = stabilize(case, candidate['id'])
        candidate['construction'] = path.relative_to(HERE).as_posix()
        candidate['construction_sha256'] = sha(path)
        trigger = candidate['trigger']
        trigger['source'] = 'native/trigger_evidence.py and original Native frame/camera evidence'
        trigger['failure_condition'] = ('measured value below threshold' if candidate['id'] == 'fallback1'
                                        else 'visible fraction below threshold')
    if case == 'controlled_1':
        for item in data['files']:
            target = HERE / item['path']
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(item['content'])
        root = copy.deepcopy(data)
        root_config = json.loads(next(item['content'] for item in root['files'] if item['path'] == 'config.json'))
        root_config['supported_case_ids'] = [x['case_id'] for x in manifest['cases']]
        root_config['status'] = 'selected_cpu_preparation'
        for item in root['files']:
            if item['path'] == 'config.json':
                item['content'] = json.dumps(root_config, indent=2, ensure_ascii=False) + '\n'
        dump(HERE / 'construction.json', root)
        dump(HERE / 'config.json', root_config)
dump(HERE / 'selected-probe-manifest.json', manifest)
print('selected source constructions', len(manifest['cases']) * 3)
