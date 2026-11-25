"""Promote exact 200-foot probes into current-runtime CPU constructions."""
import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
SIBLING = HERE.parent / 'training__C394300__NRS-484B-223-3a__motor_vehicle_driver'
SUFFIXES = ('witness_1', 'witness_2', 'numeric_1_0', 'numeric_1_1', 'numeric_1_2')
CANDIDATES = ('primary', 'fallback1', 'fallback2')
FOV = {'overview': 75, 'approach': 90, 'reference_corner': 90, 'driver_reference': 105}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + '\n')


def main():
    draft = json.loads((HERE / 'draft-execution-manifest.json').read_text())
    current = json.loads((SIBLING / 'execution-manifest.json').read_text())
    selected = copy.deepcopy(draft)
    selected['format'] = 'worker-execution-manifest'
    selected['status'] = 'selected_cpu_preparation'
    selected['runtime_manifest_sha256'] = current['runtime_manifest_sha256']
    ids = [entry['case_id'] for entry in selected['cases']]
    assert len(ids) == len(SUFFIXES) and len(set(ids)) == len(ids)
    for entry, suffix in zip(selected['cases'], SUFFIXES):
        assert entry['case_id'].endswith('__' + suffix)
        entry['kind'] = 'delivery'
        contract = json.loads((HERE / entry['measurement_contract']).read_text())
        contract['format'] = 'worker-measurement-contract'
        contract_path = HERE / f'current-measurement-{suffix}.json'
        write(contract_path, contract)
        entry['measurement_contract'] = contract_path.relative_to(HERE).as_posix()
        entry['fixture_recipe'] = ('work/' + HERE.name +
                                   '/selected-v2-' + suffix + '-recipe.json')
        entry['candidate_risk']['reason'] = (
            'Original Native full-body entry, route tracking, bidirectional lane '
            'designation and 200-foot distance need physical source review')
        entry['candidates'] = [c for c in entry['candidates'] if c['id'] in CANDIDATES[1:]]
        for candidate in CANDIDATES:
            source = HERE / 'draft-candidates' / suffix / candidate / 'construction.json'
            data = json.loads(source.read_text())
            data['status'] = 'selected_cpu_preparation'
            data['measurement_plan']['status'] = 'source_bound_cpu_preparation'
            description = data['recording_description']
            names = {c['name'] for c in description['channels']}
            for name, method in (
                ('st.centre_turn_lane', 'original bidirectional lane survey and authored map source'),
                ('kin.position', 'same-tick original Native pose and ordered body footprint'),
                ('kin.path_length', 'original body-contact-to-turn cumulative distance interval')):
                if name not in names:
                    description['channels'].append({
                        'name': name, 'unit': 'structured', 'sampling_rate_hz': 20,
                        'method': method, 'time_window': 'entire original 24 s / 480 frame attempt',
                        'reference_frame': 'original Native frame and surveyed map',
                        'uncertainty': '50 ms event brackets; boundary may be unresolved'})
            for item in data['files']:
                if item['path'] == 'finalize.py':
                    item['content'] = (HERE / 'native/finalize.py').read_text()
                if item['path'] != 'config.json':
                    continue
                config = json.loads(item['content'])
                config['status'] = 'selected_cpu_preparation'
                config['required_atoms'] = ['rel.occupies', 'kin.path_length']
                config['mandatory_channels'] = list(dict.fromkeys(
                    config['mandatory_channels'] + ['st.centre_turn_lane', 'kin.position', 'kin.path_length']))
                config['supported_case_ids'] = ids
                config['recording_description'] = description
                for camera in config['cameras']:
                    camera['fov_deg'] = FOV[camera['name']]
                item['content'] = json.dumps(config, indent=2, ensure_ascii=False) + '\n'
            target = HERE / 'selected-candidates' / suffix / candidate / 'construction.json'
            write(target, data)
            ref = entry if candidate == 'primary' else next(c for c in entry['candidates'] if c['id'] == candidate)
            ref['construction'] = target.relative_to(HERE).as_posix()
            ref['construction_sha256'] = sha(target)
            if candidate != 'primary':
                ref['trigger']['source'] = 'original same-frame Native body, pose and route source'
        if suffix == SUFFIXES[0]:
            primary = json.loads((HERE / entry['construction']).read_text())
            write(HERE / 'construction.json', primary)
            config = json.loads(next(f['content'] for f in primary['files'] if f['path'] == 'config.json'))
            write(HERE / 'config.json', config)
            for item in primary['files']:
                if item['path'] not in ('config.json',):
                    path = HERE / item['path']
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_text(item['content'])
    write(HERE / 'selected-probe-manifest.json', selected)
    print(json.dumps({'selected_cases': len(selected['cases']),
                      'candidate_constructions': len(selected['cases']) * len(CANDIDATES)}))


if __name__ == '__main__':
    main()
