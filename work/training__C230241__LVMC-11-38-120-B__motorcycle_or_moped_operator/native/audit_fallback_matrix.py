"""Independently check the unselected fallback source and target invariants."""
import copy
import hashlib
import json
from pathlib import Path


CASE = Path(__file__).resolve().parents[1]
HERE = Path(__file__).resolve().parent
EXPECTED = {
    'primary': set(),
    'fallback1': {'/candidate_id', '/spawn_point_index', '/vendor_spawn_point_index'},
    'fallback2': {'/candidate_id', '/cameras/0/location_xyz_m/0'},
    'fallback3': {'/candidate_id', '/cameras/1/fov_deg'},
}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def diff(left, right, prefix=''):
    if isinstance(left, dict) and isinstance(right, dict):
        return {item for key in left.keys() | right.keys()
                for item in diff(left.get(key), right.get(key), prefix + '/' + key)}
    if isinstance(left, list) and isinstance(right, list):
        if len(left) != len(right):
            return {prefix}
        return {item for index, (a, b) in enumerate(zip(left, right))
                for item in diff(a, b, prefix + '/' + str(index))}
    return set() if left == right else {prefix}


def content(construction, name):
    matches = [item['content'] for item in construction['files'] if item['path'] == name]
    assert len(matches) == 1, name
    return matches[0]


def verify(primary, candidate, candidate_id):
    base = json.loads(content(primary, 'config.json'))
    current = json.loads(content(candidate, 'config.json'))
    assert current['candidate_id'] == candidate_id
    assert diff(base, current) == EXPECTED[candidate_id]
    assert [item['path'] for item in candidate['files']] == [item['path'] for item in primary['files']]
    for item in primary['files']:
        if item['path'] != 'config.json':
            assert content(candidate, item['path']) == item['content'], item['path']
    assert base['requested_light_state'] == current['requested_light_state']
    assert base['vehicle_blueprint'] == current['vehicle_blueprint']
    assert base['vendor_blueprint'] == current['vendor_blueprint']
    assert base['control_phases'] == current['control_phases']
    return True


def main():
    matrix_path = HERE / 'fallback-matrix.json'
    manifest_path = CASE / 'draft-fallback-manifest.json'
    matrix = json.loads(matrix_path.read_text())
    manifest = json.loads(manifest_path.read_text())
    assert matrix['manifest_sha256'] == sha(manifest_path)
    assert manifest['status'] == 'draft_not_selected' and not manifest['delivery_ready']
    assert len(manifest['cases']) == 1
    assert [row['id'] for row in matrix['candidates']] == list(EXPECTED)
    primary_path = CASE / matrix['candidates'][0]['construction']
    primary = json.loads(primary_path.read_text())
    checked = []
    for row in matrix['candidates']:
        candidate_id = row['id']
        path = CASE / row['construction']
        assert row['construction_sha256'] == sha(path)
        candidate = json.loads(path.read_text())
        assert verify(primary, candidate, candidate_id)
        checked.append(candidate_id)
    case = manifest['cases'][0]
    assert case['construction_sha256'] == matrix['candidates'][0]['construction_sha256']
    assert [(item['id'], item['construction_sha256']) for item in case['candidates']] == [
        (item['id'], item['construction_sha256']) for item in matrix['candidates'][1:]]

    # These mutations retain the file list and exercise the semantic invariant,
    # independently of the manifest's file hashes.
    negatives = [
        ('requested_light_state', 'HighBeam'),
        ('vendor_blueprint', 'vehicle.tesla.model3'),
        ('duration_s', 29),
    ]
    for key, value in negatives:
        altered = copy.deepcopy(primary)
        config = json.loads(content(altered, 'config.json'))
        config['candidate_id'] = 'fallback1'
        config['spawn_point_index'] = 2
        config['vendor_spawn_point_index'] = 3
        config[key] = value
        for item in altered['files']:
            if item['path'] == 'config.json':
                item['content'] = json.dumps(config)
        try:
            verify(primary, altered, 'fallback1')
        except AssertionError:
            pass
        else:
            raise AssertionError('Accepted changed ' + key)
    altered = copy.deepcopy(primary)
    for item in altered['files']:
        if item['path'] == 'runner.py':
            item['content'] += '\n# altered runner\n'
    try:
        verify(primary, altered, 'primary')
    except AssertionError:
        pass
    else:
        raise AssertionError('Accepted altered runner')
    receipt = {
        'format': 'c230241-unselected-fallback-independent-audit-v1',
        'matrix_sha256': sha(matrix_path),
        'manifest_sha256': sha(manifest_path),
        'candidates_checked': checked,
        'positive_checks': len(checked),
        'negative_checks': len(negatives) + 1,
        'source_files_identical_except_config': True,
        'lamp_and_controller_target_held_fixed': True,
        'original_native_observed': False,
        'delivery_ready': False,
        'auditor_sha256': sha(Path(__file__)),
    }
    destination = HERE / 'fallback-matrix-audit.json'
    destination.write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps({'positives': len(checked), 'negatives': len(negatives) + 1,
                      'receipt_sha256': sha(destination)}))


if __name__ == '__main__':
    main()
