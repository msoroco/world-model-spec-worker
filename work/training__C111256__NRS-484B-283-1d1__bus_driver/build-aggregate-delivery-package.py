"""Materialize the six-case portable catalog entrypoint from current Native sources."""
import hashlib
import json
from pathlib import Path
import shutil
import sys

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(HERE / 'native'))
from cameras import camera_plan

CODE = ('runner.py', 'geometry.py', 'controller.py', 'engineering.py',
        'measure_walk.py', 'cameras.py', 'finalize.py',
        'physical_walk_audit.py', 'official_walk_source_audit.py',
        'physical_sweep.py')


def read(path):
    return json.loads(Path(path).read_text())


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    Path(path).write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')


def main():
    manifest = read(HERE / 'execution-manifest.json')
    plan = read(HERE / 'case-plan.json')
    selected = {entry['case_id'] for entry in manifest['cases']}
    if len(selected) != 6 or selected != {case['case_id'] for case in plan['cases']}:
        raise ValueError('Aggregate package needs all six exact selected cases')
    reference = next(entry for entry in manifest['cases']
                     if entry['case_id'].endswith('__reference'))
    sweep = next(entry for entry in manifest['cases']
                 if entry['case_id'].endswith('__right_of_way_physical_context-0000'))
    reference_bundle = read(HERE / reference['construction'])
    config = json.loads(next(file['content'] for file in reference_bundle['files']
                             if file['path'] == 'config.json'))
    config['supported_case_ids'] = sorted(selected)
    config['cameras'] = [{**camera, 'pose_strategy':
                          f"{camera['attachment']} anchored at {camera['xyz_m']} m; "
                          'verify original body, crossing and Walk pixel coverage'}
                         for camera in camera_plan('primary')]
    config['status'] = 'six_case_portable_catalog_cpu_prepared'
    write(HERE / 'config.json', config)
    files = []
    for name in CODE:
        source = HERE / 'native' / name
        if not source.is_file():
            raise ValueError('Missing current Native source: ' + name)
        shutil.copy2(source, HERE / name)
        files.append({'path': name,
                      'source': (Path('work') / HERE.name / 'native' / name).as_posix(),
                      'content': source.read_text()})
    test = HERE / 'native/test_native.py'
    target = HERE / 'tests/test_native.py'
    target.parent.mkdir(exist_ok=True)
    shutil.copy2(test, target)
    files.append({'path': 'tests/test_native.py',
                  'source': (Path('work') / HERE.name / 'native/test_native.py').as_posix(),
                  'content': test.read_text()})
    files.append({'path': 'config.json', 'content': (HERE / 'config.json').read_text()})
    sweep_bundle = read(HERE / sweep['construction'])
    construction = {'format': 'c111256-portable-six-case-catalog-v1',
                    'case_id': reference['case_id'], 'cell_id': plan['cell_id'],
                    'law_id': plan['law_id'], 'actor': plan['actor'],
                    'entrypoint': 'runner.py', 'files': files,
                    'measurement_plan': {'source': 'case-plan.json',
                                         'requirements': plan['requirement_dispositions'],
                                         'per_case_contracts': {
                                             entry['case_id']: entry['measurement_contract']
                                             for entry in manifest['cases']}},
                    'recording_description': sweep_bundle['recording_description'],
                    'static_checks': ['exact six-case identity', 'four source cameras',
                                      'full-body bus and pedestrian source joins',
                                      'official Walk pixel review before original acceptance'],
                    'termination_rules': sweep_bundle['termination_rules'],
                    'mechanisms': sweep_bundle['mechanisms'],
                    'status': 'cpu_prepared_original_source_unverified'}
    write(HERE / 'construction.json', construction)
    plan['camera_plan'] = {
        'profile': 'overview1080-capability', 'duration_s': config['duration_s'],
        'composition': 'synchronized_four_view_primary',
        'coverage': [{'subject': camera['purpose'], 'interval': 'startup through clearance',
                      'view': camera['name']} for camera in config['cameras']],
        'original_visibility_verified': False}
    write(HERE / 'case-plan.json', plan)
    print(json.dumps({'selected_cases': 6, 'root_files': len(files),
                      'construction_sha256': sha(HERE / 'construction.json'),
                      'config_sha256': sha(HERE / 'config.json'),
                      'camera_plan_profile': plan['camera_plan']['profile'],
                      'original_visibility_verified': False}, sort_keys=True))


if __name__ == '__main__':
    main()
