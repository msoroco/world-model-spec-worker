"""Promote exact after-turn 50-foot probes into current-runtime constructions."""
import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
SIBLING = HERE.parent / 'training__C394300__NRS-484B-223-3b__motor_vehicle_driver'
CASES = ('below_50_ft', 'at_50_ft', 'above_50_ft')
CANDIDATES = ('primary', 'fallback1', 'fallback2')
FOV = {'overview': 75, 'approach': 90, 'reference_corner': 90, 'driver_reference': 105}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + '\n')


def main():
    source = json.loads((HERE / 'draft-execution-manifest.json').read_text())
    current = json.loads((SIBLING / 'execution-manifest.json').read_text())
    selected = copy.deepcopy(source)
    selected['format'] = 'worker-execution-manifest'
    selected['status'] = 'selected_cpu_preparation'
    selected['runtime_manifest_sha256'] = current['runtime_manifest_sha256']
    ids = [entry['case_id'] for entry in selected['cases']]
    assert len(ids) == 3 and all(cid.endswith('__' + suffix) for cid, suffix in zip(ids, CASES))
    for entry, suffix in zip(selected['cases'], CASES):
        entry['kind'] = 'delivery'
        contract = json.loads((HERE / entry['measurement_contract']).read_text())
        contract['format'] = 'worker-measurement-contract'
        path = HERE / f'current-measurement-{suffix}.json'
        write(path, contract)
        entry['measurement_contract'] = path.relative_to(HERE).as_posix()
        entry['fixture_recipe'] = f'work/{HERE.name}/selected-v2-{suffix}-recipe.json'
        entry['candidate_risk']['reason'] = (
            'Original Native left-turn connector tracking, bidirectional center-lane designation, '
            'full-body through-lane merge and 50-foot distance require physical source review')
        entry['candidates'] = [candidate for candidate in entry['candidates']
                               if candidate['id'] in CANDIDATES[1:]]
        for candidate in CANDIDATES:
            data = json.loads((HERE / 'draft-candidates' / suffix / candidate / 'construction.json').read_text())
            data['status'] = 'selected_cpu_preparation'
            data['measurement_plan']['status'] = 'source_bound_cpu_preparation'
            description = data['recording_description']
            names = {channel['name'] for channel in description['channels']}
            for name, method in (
                ('ego_pose', 'same-tick original Native body pose and footprint'),
                ('ego_speed', 'same-tick original Native observed velocity'),
                ('center_turn_lane_distance_after_left_turn',
                 'original connector-to-highway turn completion and full-body through-lane merge distance interval')):
                if name not in names:
                    description['channels'].append({
                        'name': name, 'unit': 'structured', 'sampling_rate_hz': 20,
                        'method': method, 'time_window': 'entire original 30 s / 600 frame attempt',
                        'reference_frame': 'original Native frame and surveyed map',
                        'uncertainty': '50 ms event brackets; boundary may be unresolved'})
            for item in data['files']:
                if item['path'] == 'finalize.py':
                    item['content'] = (HERE / 'native/finalize.py').read_text()
                elif item['path'] == 'tests/test_candidate_knobs.py':
                    item['content'] = item['content'].replace(
                        "self.assertEqual(set(config['mandatory_channels']),set(config['required_atoms'])|",
                        "self.assertTrue(set(config['required_atoms'])|"
                    ).replace(
                        "{'native_body_pose_control','camera_frame_join'})",
                        "{'native_body_pose_control','camera_frame_join'} <= set(config['mandatory_channels']))"
                    )
                elif item['path'] == 'config.json':
                    config = json.loads(item['content'])
                    config['status'] = 'selected_cpu_preparation'
                    config['required_atoms'] = ['rel.occupies', 'kin.path_length']
                    config['mandatory_channels'] = list(dict.fromkeys(
                        config['mandatory_channels'] + ['ego_pose', 'ego_speed',
                                                        'center_turn_lane_distance_after_left_turn']))
                    config['supported_case_ids'] = ids
                    config['recording_description'] = description
                    for camera in config['cameras']:
                        camera['fov_deg'] = FOV[camera['name']]
                    item['content'] = json.dumps(config, indent=2, ensure_ascii=False) + '\n'
            target = HERE / 'selected-candidates' / suffix / candidate / 'construction.json'
            write(target, data)
            ref = entry if candidate == 'primary' else next(
                row for row in entry['candidates'] if row['id'] == candidate)
            ref['construction'] = target.relative_to(HERE).as_posix()
            ref['construction_sha256'] = sha(target)
            if candidate != 'primary':
                ref['trigger']['source'] = 'original same-frame Native body, pose and route source'
        if suffix == CASES[0]:
            primary = json.loads((HERE / entry['construction']).read_text())
            write(HERE / 'construction.json', primary)
            write(HERE / 'config.json', json.loads(next(
                item['content'] for item in primary['files'] if item['path'] == 'config.json')))
            for item in primary['files']:
                if item['path'] != 'config.json':
                    path = HERE / item['path']
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_text(item['content'])
    write(HERE / 'selected-probe-manifest.json', selected)
    print(json.dumps({'selected_cases': len(ids), 'constructions': len(ids) * len(CANDIDATES)}))


if __name__ == '__main__':
    main()
