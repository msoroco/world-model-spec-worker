"""Materialize the selected portable root entrypoint and exact source contract."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, sort_keys=True, indent=2) + '\n', encoding='utf-8')


def main():
    manifest = json.loads((HERE / 'selected-30s-draft-execution-manifest.json').read_text())
    first = manifest['cases'][0]
    construction = json.loads((HERE / first['construction']).read_text())
    config = json.loads(next(item['content'] for item in construction['files'] if item['path'] == 'config.json'))
    config['supported_case_ids'] = [item['case_id'] for item in manifest['cases']]
    config['case_plan_sha256'] = sha(HERE / 'case-plan.json')
    for item in construction['files']:
        if item['path'] == 'config.json':
            item['content'] = json.dumps(config, sort_keys=True, indent=2) + '\n'
        target = HERE / item['path']
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(item['content'], encoding='utf-8')
    construction['static_checks'] = [
        'Two opposing OpenDRIVE driving lanes and one connected sidewalk lane',
        '600 ordered 20 Hz motorcycle request samples and exact case/candidate identity',
        'Four synchronized original camera sources and saved Native body/lane/frame join',
    ]
    construction['termination_rules'] = ['30 s source window', 'record Native failure and restoration status']
    construction['mechanisms'] = ['CARLA motorcycle controller follows source-hashed longitudinal/lateral track',
                                  'saved finalizer measures full motorcycle body overlap and City spatial context']
    write(HERE / 'construction.json', construction)
    print(json.dumps({'root_construction_sha256': sha(HERE / 'construction.json'),
                      'root_config_sha256': sha(HERE / 'config.json')}))


if __name__ == '__main__':
    main()
