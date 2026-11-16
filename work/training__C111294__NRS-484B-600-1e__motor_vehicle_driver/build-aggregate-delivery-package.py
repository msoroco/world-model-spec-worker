"""Materialize the four-case portable speed package and capture plan."""
import hashlib
import json
import shutil
from pathlib import Path

HERE = Path(__file__).resolve().parent
CODE = ('runner.py', 'geometry.py', 'engineering.py', 'cameras.py',
        'measure_speed.py', 'finalize.py')
TESTS = ('test_geometry_speed.py', 'test_runner.py')


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
    if len(selected) != 4 or selected != {case['case_id'] for case in plan['cases']}:
        raise ValueError('Four exact selected boundary cases required')
    first = next(entry for entry in manifest['cases']
                 if entry['case_id'].endswith('__below_80_mph'))
    bundle = read(HERE / first['construction'])
    config = json.loads(next(item['content'] for item in bundle['files']
                             if item['path'] == 'config.json'))
    config['supported_case_ids'] = sorted(selected)
    config['cameras'] = [{**camera, 'pose_strategy':
                          f"{camera['attachment']} anchored at {camera['xyz_m']} m; "
                          'verify original vehicle, road context and speed evidence'}
                         for camera in config['cameras']]
    config['status'] = 'four_case_portable_catalog_cpu_prepared'
    write(HERE / 'config.json', config)

    files = []
    for name in CODE:
        source = HERE / 'native' / name
        target = HERE / name
        shutil.copy2(source, target)
        files.append({'path': name,
                      'source': (Path('work') / HERE.name / 'native' / name).as_posix(),
                      'content': source.read_text()})
    (HERE / 'tests').mkdir(exist_ok=True)
    for name in TESTS:
        source = HERE / 'native' / name
        target = HERE / 'tests' / name
        shutil.copy2(source, target)
        files.append({'path': 'tests/' + name,
                      'source': (Path('work') / HERE.name / 'native' / name).as_posix(),
                      'content': source.read_text()})
    files.append({'path': 'config.json', 'content': (HERE / 'config.json').read_text()})

    construction = {'format': 'c111294-portable-four-case-catalog-v1',
                    'case_id': first['case_id'], 'cell_id': plan['cell_id'],
                    'law_id': plan['law_id'], 'actor': plan['actor'],
                    'entrypoint': 'runner.py', 'files': files,
                    'measurement_plan': {'source': 'case-plan.json',
                                         'requirements': plan['requirement_dispositions'],
                                         'per_case_contracts': {entry['case_id']: entry['measurement_contract']
                                                                for entry in manifest['cases']}},
                    'recording_description': bundle['recording_description'],
                    'static_checks': ['four exact boundary requests', 'four original source cameras',
                                      'source-derived 20 Hz Native velocity',
                                      'uncertainty-preserving exact-80 relation'],
                    'termination_rules': bundle['termination_rules'],
                    'mechanisms': bundle['mechanisms'],
                    'status': 'cpu_prepared_original_velocity_unverified'}
    write(HERE / 'construction.json', construction)

    plan['source_observation_mapping']['kin.speed'] = {
        'evidence': 'Derived from retained original Native velocity in saved finalization; original speed unverified.',
        'channels': ['observed_speed'], 'source_refs': ['native_samples.jsonl']}
    plan['source_observation_mapping']['kin.velocity'] = {
        'evidence': 'Retained original three-axis Native velocity and frame identity; original speed unverified.',
        'channels': ['ego_speed'], 'source_refs': ['native_samples.jsonl']}
    plan['source_observation_mapping']['ru.subject'] = {
        'evidence': 'Original Native actor pose and role readback; vehicle operation unverified.',
        'channels': ['ego_pose'], 'source_refs': ['native_samples.jsonl']}
    plan['camera_plan'] = {'profile': 'overview1080-capability',
                           'duration_s': config['duration_s'],
                           'composition': 'synchronized_four_view_primary',
                           'coverage': [
                               {'subject': 'ego vehicle body and roadway',
                                'interval': 'startup through final speed observation', 'view': 'overview'},
                               {'subject': 'forward road and traffic context',
                                'interval': 'startup through final speed observation', 'view': 'approach'},
                               {'subject': 'fixed roadway and other vehicle context',
                                'interval': 'startup through final speed observation', 'view': 'reference_corner'},
                               {'subject': 'driver vehicle and controls context',
                                'interval': 'startup through final speed observation', 'view': 'driver_reference'}],
                           'original_visibility_verified': False}
    write(HERE / 'case-plan.json', plan)
    manifest['selection_review']['case_plan_sha256'] = sha(HERE / 'case-plan.json')
    write(HERE / 'execution-manifest.json', manifest)
    print(json.dumps({'selected_cases': len(selected), 'root_files': len(files),
                      'construction_sha256': sha(HERE / 'construction.json'),
                      'config_sha256': sha(HERE / 'config.json'),
                      'case_plan_sha256': sha(HERE / 'case-plan.json'),
                      'manifest_sha256': sha(HERE / 'execution-manifest.json'),
                      'original_velocity_verified': False}))


if __name__ == '__main__':
    main()
