"""Select current-runtime pedestrian entry diagnostics with supported Core atoms."""
import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
CASES = ('reference', 'contrast')
CANDIDATES = ('primary', 'fallback1', 'fallback2')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + '\n')


def main():
    draft = json.loads((HERE / 'draft-primary-manifest.json').read_text())
    selected = {'format': 'worker-execution-manifest', 'assignment_id': HERE.name,
                'runtime_manifest_sha256': sha(ROOT / 'runtime/SOURCE-MANIFEST.json'),
                'status': 'selected_cpu_preparation', 'cases': []}
    ids = [HERE.name + '__' + suffix for suffix in CASES]
    native_sources = {path.name: path for path in (HERE / 'native').glob('*.py')}
    for suffix in CASES:
        original = next(row for row in draft['cases'] if row['case_id'].endswith('__' + suffix))
        entry = copy.deepcopy(original)
        entry['kind'] = 'delivery'
        entry['id'] = 'primary'
        entry['fixture_recipe'] = f'work/{HERE.name}/selected-v2-{suffix}-recipe.json'
        dispositions = json.loads((HERE / 'case-plan.json').read_text())['requirement_dispositions']
        requirements = []
        for index, disposition in enumerate(dispositions):
            output_key, inputs = (
                ('signal_context', ['native-signal-frames.jsonl',
                                    'governing-device-authority.json',
                                    'independent-review.json']) if index == 0 else
                ('road_entry', ['native-pedestrian-frames.jsonl',
                                'road-boundary.json', 'independent-review.json']) if index == 1 else
                ('other_device_context', ['native-pedestrian-device-frames.jsonl',
                                          'independent-review.json']))
            requirements.append({'disposition_index': index,
                                 'requirement': disposition['requirement'],
                                 'source': disposition['source'],
                                 'output_key': output_key, 'method': 'finalize',
                                 'value_type': 'object', 'kind': 'measured',
                                 'inputs': inputs})
        contract = {'format': 'worker-measurement-contract',
                    'case_id': entry['case_id'], 'requirements': requirements,
                    'negative': {'remove': ['native-pedestrian-frames.jsonl'],
                                 'error_contains': 'Missing required source: native-pedestrian-frames.jsonl'}}
        contract_path = HERE / f'current-measurement-{suffix}.json'
        write(contract_path, contract)
        entry['measurement_contract'] = contract_path.relative_to(HERE).as_posix()
        entry['candidates'] = [row for row in entry['candidates'] if row['id'] in CANDIDATES[1:]]
        entry['candidate_risk'] = {'status': 'physical', 'reason':
            'Original Native walker spawn and 600-frame path may miss the source-reviewed road boundary; alternate clearance and speed are measured retries.'}
        for candidate in CANDIDATES:
            ref = entry if candidate == 'primary' else next(
                row for row in entry['candidates'] if row['id'] == candidate)
            source = HERE / ref['construction']
            construction = json.loads(source.read_text())
            construction['status'] = 'selected_cpu_preparation'
            construction['measurement_plan'] = {
                'status': 'source_bound_cpu_preparation',
                'method': '600-frame original Native pedestrian footprint transition at independently reviewed highway boundary, governed signal, and other-device permission.'}
            for item in construction['files']:
                if item['path'] != 'config.json':
                    source = native_sources.get(Path(item['path']).name)
                    if source is not None:
                        item['content'] = source.read_text()
                    continue
                config = json.loads(item['content'])
                config['required_atoms'] = [atom for atom in config['required_atoms']
                                            if atom != 'dev.pedestrian_signal']
                config['supported_case_ids'] = ids
                config['status'] = 'selected_cpu_preparation'
                for camera in config['cameras']:
                    camera['fov_deg'] = 90
                    camera['pose_strategy'] = 'source_visible_signal_and_boundary'
                item['content'] = json.dumps(config, indent=2, ensure_ascii=False) + '\n'
            path = HERE / 'selected-candidates' / suffix / candidate / 'construction.json'
            write(path, construction)
            ref['construction'] = path.relative_to(HERE).as_posix()
            ref['construction_sha256'] = sha(path)
        selected['cases'].append(entry)
    write(HERE / 'selected-probe-manifest.json', selected)
    primary = json.loads((HERE / selected['cases'][0]['construction']).read_text())
    write(HERE / 'construction.json', primary)
    for item in primary['files']:
        path = HERE / item['path']
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(item['content'])
    print(json.dumps({'cases': len(selected['cases']),
                      'constructions': len(CASES) * len(CANDIDATES),
                      'runtime_manifest_sha256': selected['runtime_manifest_sha256']}))


if __name__ == '__main__':
    main()
