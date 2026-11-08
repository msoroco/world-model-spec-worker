"""Measure three distinct fallback crossings in both exact park case families."""
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SOURCE = ROOT / '.runtime-work/c10052/fallback-triggers-v1'
OUTPUT = ROOT / '.runtime-work/c10052/park-case-triggers-v1'
NAMES = ('primary', 'fallback1', 'fallback2', 'fallback3')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n')


def load(path, key):
    spec = importlib.util.spec_from_file_location(key, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main():
    if OUTPUT.exists():
        raise ValueError('Retain prior park trigger proof')
    OUTPUT.mkdir(parents=True)
    manifest_path = HERE / 'draft-park-execution-manifest.json'
    entries = json.loads(manifest_path.read_text())['cases']
    proof = []
    for entry in entries:
        suffix = entry['case_id'].rsplit('__', 1)[-1]
        for name in NAMES:
            ref = entry if name == 'primary' else next(c for c in entry['candidates'] if c['id'] == name)
            bundle = json.loads((HERE / ref['construction']).read_text())
            files = {f['path']: f['content'] for f in bundle['files']}
            folder = OUTPUT / suffix / name
            folder.mkdir(parents=True)
            source_name = 'baseline' if name == 'primary' else name
            for file in ('native_samples.jsonl', 'camera_visibility.jsonl'):
                shutil.copyfile(SOURCE / source_name / file, folder / file)
            (folder / 'config.json').write_text(files['config.json'])
            (folder / 'fallback_triggers.py').write_text(files['fallback_triggers.py'])
            write(folder / 'trigger-sources.json', {
                'format': 'c10052-trigger-sources-v1',
                'source_kind': 'synthetic_cpu_fixture',
                'route_survey_passed': True,
                'sha256': {file: sha(folder / file) for file in
                           ('native_samples.jsonl', 'camera_visibility.jsonl', 'config.json')}})
            meter = load(folder / 'fallback_triggers.py', 'park_' + suffix + '_' + name)
            measurement = meter.evaluate(folder)
            assert measurement['case_suffix'] == suffix and measurement['frames'] == 480
            assert all(measurement[f'fallback{i}_trigger_measured'] is (name == f'fallback{i}')
                       for i in range(1, 4))
            write(folder / 'measurement.json', measurement)
            negative = OUTPUT / suffix / (name + '-negative')
            shutil.copytree(folder, negative)
            (negative / 'camera_visibility.jsonl').write_bytes(
                (negative / 'camera_visibility.jsonl').read_bytes() + b' ')
            try:
                meter.evaluate(negative)
            except ValueError as error:
                assert 'Trigger source hash differs' in str(error)
            else:
                raise AssertionError('Changed park trigger source accepted')
            proof.append({'case_id': entry['case_id'], 'candidate': name,
                          'construction_sha256': sha(HERE / ref['construction']),
                          'source_root': folder.relative_to(ROOT).as_posix(),
                          'source_manifest_sha256': sha(folder / 'trigger-sources.json'),
                          'measurement_sha256': sha(folder / 'measurement.json'),
                          'changed_visibility_rejected': True})
    summary = {'format': 'c10052-park-case-trigger-proof-v1', 'passed': True,
               'manifest_sha256': sha(manifest_path), 'rows': proof,
               'selected': False, 'physical_observation_claimed': False}
    write(HERE / 'park-case-trigger-summary.json', summary)
    print(json.dumps({'passed': True, 'rows': len(proof),
                      'measured_fallback_crossings': 6, 'negative_rejections': 8}))


if __name__ == '__main__':
    main()
