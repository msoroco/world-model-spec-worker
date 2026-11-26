"""Bind passing current-runtime offline receipts to exact selected cases."""
import argparse
import hashlib
import json
from pathlib import Path

FOLDER = Path(__file__).resolve().parent.parent
REPO = FOLDER.parent.parent


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    Path(path).write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')


def bind(version):
    manifest = FOLDER / 'selected-construction-manifest.json'
    data = json.loads(manifest.read_text())
    for i, entry in enumerate(data['cases'], 1):
        for variant, obj in [('primary', entry)] + [
                (item['id'], item) for item in entry['candidates']]:
            scratch = REPO / '.runtime-work' / f'c229977-offline-{version}-probe_{i}-{variant}'
            source = scratch / 'offline.log'
            if not source.is_file():
                raise ValueError('Missing passing offline source: ' + str(source))
            content = '\n'.join(line.rstrip() for line in source.read_text().splitlines()).rstrip() + '\n'
            log = FOLDER / f'selected-probe-{i}' / f'proof-{variant}.log'
            log.write_text(content)
            obj['offline'] = {
                'command': f'.venv-cpu/bin/python -B runtime.py offline --manifest '
                           f'{manifest.relative_to(REPO)} --case {entry["case_id"]} '
                           f'--candidate {variant} --output {scratch.relative_to(REPO)}',
                'exit_code': 0,
                'construction_sha256': obj['construction_sha256'],
                'log': str(log.relative_to(FOLDER)),
                'log_sha256': sha(log)}
            if variant == 'primary':
                obj['measurement_contract'] = 'measurement-contract.json'
                obj['fixture_recipe'] = str(
                    (FOLDER / f'diagnostic-recipe-probe_{i}.json').relative_to(REPO))
                obj['measurement_procedure'] = {'entrypoint': 'finalize_sidewalk.py'}
                obj['native_handoff'] = {'python_env_var': 'CARLA_PYTHON',
                                         'host_env_var': 'CARLA_HOST',
                                         'port_env_var': 'CARLA_PORT'}
    data['status'] = 'public_compatibility_pending'
    write(manifest, data)
    execution = dict(data, format='worker-execution-manifest')
    write(FOLDER / 'execution-manifest.json', execution)
    cases_path = FOLDER / 'proposals' / 'cases.json'
    cases = json.loads(cases_path.read_text())
    for case, entry in zip(cases['cases'], data['cases']):
        case['recording_description'] = json.loads(
            (FOLDER / entry['construction']).read_text())['recording_description']
    write(cases_path, cases)
    return sha(FOLDER / 'execution-manifest.json')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('version')
    args = parser.parse_args()
    print(bind(args.version))
