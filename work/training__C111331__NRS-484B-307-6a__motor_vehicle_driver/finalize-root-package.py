"""Bind root portable catalog to the selected pair and capture profile."""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def read(name):
    return json.loads((HERE / name).read_text())


def write(name, value):
    (HERE / name).write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')


def main():
    config = read('config.json')
    fov = {'overview': 90, 'approach': 90, 'reference_corner': config['camera_plan']['horizontal_fov_deg'],
           'driver_reference': 90}
    for camera in config['cameras']:
        camera['fov_deg'] = fov[camera['name']]
    config['required_atoms'] = ['kin.speed']
    config['source_packets'] = []
    write('config.json', config)
    construction = read('construction.json')
    plan = read('case-plan.json')
    manifest = read('execution-manifest.json')
    construction['measurement_plan'] = {
        'source': 'case-plan.json', 'requirements': plan['requirement_dispositions'],
        'per_case_contracts': {entry['case_id']: entry['measurement_contract']
                               for entry in manifest['cases']}}
    for item in construction['files']:
        if item['path'] == 'config.json':
            item['content'] = (HERE / 'config.json').read_text()
    write('construction.json', construction)
    print(json.dumps({'case_count': len(manifest['cases']), 'cameras': [c['name'] for c in config['cameras']],
                      'required_atoms': config['required_atoms']}))


if __name__ == '__main__':
    main()
