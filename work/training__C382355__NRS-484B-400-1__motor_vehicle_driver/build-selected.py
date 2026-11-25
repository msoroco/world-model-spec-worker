"""Select both source-defined NRS 484B.400(1) lane alternatives."""
import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ASSIGNMENT = HERE.name
CASES = ('witness_1', 'witness_2', 'extreme_right_1', 'extreme_right_2')
CANDIDATES = ('primary', 'fallback1', 'fallback2')
FOV = {'overview': 90, 'approach': 90, 'reference_corner': 90,
       'driver_reference': 90}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')


def main():
    draft = json.loads((HERE / 'draft-execution-manifest.json').read_text())
    current = json.loads((HERE.parent / 'training__C394300__NRS-484B-223-3c__motor_vehicle_driver' /
                          'execution-manifest.json').read_text())
    selected = {'format': 'worker-execution-manifest', 'assignment_id': ASSIGNMENT,
                'runtime_manifest_sha256': current['runtime_manifest_sha256'],
                'status': 'selected_cpu_preparation', 'cases': []}
    ids = [ASSIGNMENT + '__' + suffix for suffix in CASES]
    source_files = {path.name: path for path in (HERE / 'native').glob('*.py')}
    for suffix in CASES:
        base_suffix = 'witness_' + suffix[-1] if suffix.startswith('extreme_right_') else suffix
        original = next(row for row in draft['cases'] if row['case_id'].endswith('__' + base_suffix))
        entry = copy.deepcopy(original)
        entry['case_id'] = ASSIGNMENT + '__' + suffix
        entry['kind'] = 'delivery'
        entry['candidate_risk']['reason'] = (
            'Native map right-only design, required approach lane and turn connector, '
            'full-body occupancy, route tracking and original pixels require source review')
        entry['candidates'] = [row for row in entry['candidates'] if row['id'] in CANDIDATES[1:]]
        contract = json.loads((HERE / original['measurement_contract']).read_text())
        contract['format'] = 'worker-measurement-contract'
        contract['case_id'] = entry['case_id']
        contract['requirements'][0]['inputs'] = ['native_samples.jsonl', 'road_geometry.json']
        contract_path = HERE / f'current-measurement-{suffix}.json'
        write(contract_path, contract)
        entry['measurement_contract'] = contract_path.relative_to(HERE).as_posix()
        entry['fixture_recipe'] = f'work/{ASSIGNMENT}/selected-v2-{suffix}-recipe.json'
        for candidate in CANDIDATES:
            source = HERE / 'draft-candidates' / base_suffix / candidate / 'construction.json'
            construction = json.loads(source.read_text())
            construction['case_id'] = entry['case_id']
            construction['status'] = 'selected_cpu_preparation'
            construction['measurement_plan']['status'] = 'source_bound_cpu_preparation'
            construction['measurement_plan']['method'] = (
                'Original Native map survey and body/lane rows for qualifying right-only '
                'or alternative extreme-right approach and turn; see qualifying_lane.py')
            construction['static_checks'].append('both frozen 400(1) lane alternatives')
            for item in construction['files']:
                source_name = Path(item['path']).name
                if source_name in source_files:
                    item['content'] = source_files[source_name].read_text()
                if item['path'] == 'config.json':
                    config = json.loads(item['content'])
                    config['case_id'] = entry['case_id']
                    config['selected_case_id'] = entry['case_id']
                    config['case_suffix'] = suffix
                    config['case'] = {'case_id': entry['case_id']}
                    config['supported_case_ids'] = ids
                    config['status'] = 'selected_cpu_preparation'
                    config['right_only_turn_lane_design_requested'] = suffix.startswith('witness_')
                    for camera in config['cameras']:
                        camera['fov_deg'] = FOV[camera['name']]
                    item['content'] = json.dumps(config, indent=2, ensure_ascii=False) + '\n'
            target = HERE / 'selected-candidates' / suffix / candidate / 'construction.json'
            write(target, construction)
            ref = entry if candidate == 'primary' else next(
                row for row in entry['candidates'] if row['id'] == candidate)
            ref['construction'] = target.relative_to(HERE).as_posix()
            ref['construction_sha256'] = sha(target)
            if candidate != 'primary':
                ref['trigger']['source'] = 'original Native map and same-frame body, pose and camera sources'
        selected['cases'].append(entry)
    write(HERE / 'selected-probe-manifest.json', selected)
    primary = json.loads((HERE / selected['cases'][0]['construction']).read_text())
    write(HERE / 'construction.json', primary)
    root_config = json.loads(next(item['content'] for item in primary['files'] if item['path'] == 'config.json'))
    write(HERE / 'config.json', root_config)
    print(json.dumps({'cases': len(selected['cases']), 'constructions': len(CASES) * len(CANDIDATES),
                      'runtime_manifest_sha256': selected['runtime_manifest_sha256']}))


if __name__ == '__main__':
    main()
