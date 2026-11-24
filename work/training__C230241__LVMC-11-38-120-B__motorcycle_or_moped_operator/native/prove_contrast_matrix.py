"""Audit unselected reference/contrast construction and pinned offline logs."""
import copy
import hashlib
import json
from pathlib import Path


CASE = Path(__file__).resolve().parents[1]
HERE = Path(__file__).resolve().parent
NAMES = ('primary', 'fallback1', 'fallback2', 'fallback3')


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bundle(group, candidate):
    if group == 'draft-primary' and candidate != 'primary':
        group = 'draft-candidates'
    path = CASE / group / ('contrast' if group == 'draft-contrast' else 'reference') / candidate / 'construction.json'
    data = json.loads(path.read_text())
    files = {item['path']: item['content'] for item in data['files']}
    return path, data, files, json.loads(files['config.json'])


def changed(left, right, prefix=''):
    if isinstance(left, dict) and isinstance(right, dict):
        return {part for key in left.keys() | right.keys()
                for part in changed(left.get(key), right.get(key), prefix + '/' + key)}
    if isinstance(left, list) and isinstance(right, list):
        if len(left) != len(right):
            return {prefix}
        return {part for index, (a, b) in enumerate(zip(left, right))
                for part in changed(a, b, prefix + '/' + str(index))}
    return set() if left == right else {prefix}


def audit():
    matrix_path = HERE / 'contrast-matrix.json'
    manifest_path = CASE / 'draft-contrast-manifest.json'
    matrix = json.loads(matrix_path.read_text())
    assert matrix['manifest_sha256'] == digest(manifest_path)
    assert matrix['contrast_runner_sha256'] == digest(HERE / 'contrast_runner.py')
    rows = []
    for row in matrix['candidates']:
        name = row['id']
        assert name in NAMES
        reference_path, reference, ref_files, ref_config = bundle('draft-primary', name)
        contrast_path, contrast, con_files, con_config = bundle('draft-contrast', name)
        assert digest(contrast_path) == row['construction_sha256']
        assert contrast['case_id'] == matrix['case_id']
        assert reference['case_id'].endswith('__reference')
        assert set(ref_files) == set(con_files)
        assert all(ref_files[key] == con_files[key] for key in ref_files if key not in ('config.json', 'runner.py'))
        assert con_files['runner.py'] == (HERE / 'contrast_runner.py').read_text()
        expected = copy.deepcopy(ref_config)
        expected.update({'case_id': matrix['case_id'],
                         'selected_case_id': matrix['case_id'],
                         'case': 'contrast', 'requested_light_state': 'Position'})
        assert con_config == expected
        assert ref_config['requested_light_state'] == 'LowBeam|Position'
        assert changed(ref_config, con_config) == {
            '/case_id', '/selected_case_id', '/case', '/requested_light_state'}
        offline_path = HERE / ('contrast-offline-' + name + '.log')
        offline = offline_path.read_text()
        assert 'Ran 4 tests' in offline and '\nOK\n' in offline
        assert '"candidate_id": "' + name + '"' in offline
        assert '"carla_contacted": false' in offline
        rows.append({'candidate': name, 'construction_sha256': digest(contrast_path),
                     'reference_construction_sha256': digest(reference_path),
                     'offline_log_sha256': digest(offline_path), 'offline_tests': 4})
    assert [row['candidate'] for row in rows] == list(NAMES)
    native = (HERE / 'native_runner.py').read_text()
    expected_runner = native.replace("PREFIX + 'reference'", "PREFIX + 'contrast'")
    expected_runner = expected_runner.replace("== 'LowBeam|Position'", "== 'Position'")
    expected_runner = expected_runner.replace('carla.VehicleLightState.LowBeam | carla.VehicleLightState.Position', 'carla.VehicleLightState.Position')
    expected_runner = expected_runner.replace("'light_state_requested': 'LowBeam|Position'", "'light_state_requested': 'Position'")
    assert expected_runner == (HERE / 'contrast_runner.py').read_text()
    receipt = {'format': 'c230241-unselected-contrast-audit-v1',
               'assignment_id': CASE.name, 'case_id': matrix['case_id'],
               'manifest_sha256': digest(manifest_path),
               'matrix_sha256': digest(matrix_path),
               'runner_sha256': digest(HERE / 'contrast_runner.py'),
               'candidates': rows, 'offline_tests_passed': 16,
               'simulation_started': False, 'physical_visibility_verified': False,
               'selected_delivery_cases': 0}
    out = HERE / 'contrast-offline-proof.json'
    out.write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps({'proof_sha256': digest(out), 'checks': len(rows), 'tests': 16}))


if __name__ == '__main__':
    audit()
