"""Build source-preserving unselected lighting capture fallbacks.

Each fallback changes one engineering choice. None requests a different lamp
outcome or claims calibrated original light visibility.
"""
import copy
import hashlib
import json
from pathlib import Path

from native_runner import check


ROOT = Path(__file__).resolve().parents[1]
CASE = ROOT.name + '__reference'
PRIMARY = ROOT / 'draft-primary/reference/primary/construction.json'
CANDIDATES = ('primary', 'fallback1', 'fallback2', 'fallback3')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def config_of(construction):
    return json.loads(next(item['content'] for item in construction['files']
                           if item['path'] == 'config.json'))


def modify(base, candidate):
    value = copy.deepcopy(base)
    value['candidate_id'] = candidate
    if candidate == 'fallback1':
        value['spawn_point_index'] = 2
        value['vendor_spawn_point_index'] = 3
        knob = 'spawn_pair_index'
    elif candidate == 'fallback2':
        value['cameras'][0]['location_xyz_m'][0] = -8
        knob = 'overview_camera_distance'
    elif candidate == 'fallback3':
        value['cameras'][1]['fov_deg'] = 80
        knob = 'approach_camera_fov'
    else:
        knob = 'primary'
    return value, knob


def changed_paths(left, right, prefix=''):
    if isinstance(left, dict) and isinstance(right, dict):
        keys = left.keys() | right.keys()
        return [path for key in keys
                for path in changed_paths(left.get(key), right.get(key),
                                          prefix + '/' + key)]
    if isinstance(left, list) and isinstance(right, list):
        if len(left) != len(right):
            return [prefix]
        return [path for index, (a, b) in enumerate(zip(left, right))
                for path in changed_paths(a, b, prefix + '/' + str(index))]
    return [] if left == right else [prefix]


def build():
    primary = json.loads(PRIMARY.read_text())
    original = config_of(primary)
    assert original['case_id'] == CASE and original['candidate_id'] == 'primary'
    assert check(original)['frames'] == 600
    permitted = {
        'fallback1': {'/candidate_id', '/spawn_point_index',
                      '/vendor_spawn_point_index'},
        'fallback2': {'/candidate_id', '/cameras/0/location_xyz_m/0'},
        'fallback3': {'/candidate_id', '/cameras/1/fov_deg'},
    }
    entries = []
    for candidate in CANDIDATES:
        config, knob = modify(original, candidate)
        assert check(config)['candidate_id'] == candidate
        diff = set(changed_paths(original, config))
        assert diff == permitted.get(candidate, set()), (candidate, diff)
        construction = copy.deepcopy(primary)
        construction['files'] = [dict(item, content=json.dumps(config, indent=2) + '\n')
                                 if item['path'] == 'config.json' else item
                                 for item in construction['files']]
        if candidate == 'primary':
            path = PRIMARY
            assert construction == primary
        else:
            path = ROOT / 'draft-candidates/reference' / candidate / 'construction.json'
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(construction, indent=2) + '\n')
        entries.append({'id': candidate, 'construction': str(path.relative_to(ROOT)),
                        'construction_sha256': sha(path), 'engineering_knob': knob,
                        'changed_config_paths': sorted(diff)})
    manifest = {
        'assignment_id': ROOT.name,
        'format': 'worker-unselected-draft-construction-manifest-v1',
        'status': 'draft_not_selected',
        'cases': [{
            'case_id': CASE, 'construction': entries[0]['construction'],
            'construction_sha256': entries[0]['construction_sha256'],
            'candidates': [{key: row[key] for key in ('id', 'construction',
                                                      'construction_sha256')}
                           for row in entries[1:]],
            'candidate_risk': {
                'status': 'physical',
                'reason': 'Original Native lamp model, mounted tail lamp, calibrated range, vendor identity and site geometry require review.'}}],
        'original_native_observed': False, 'delivery_ready': False}
    destination = ROOT / 'draft-fallback-manifest.json'
    destination.write_text(json.dumps(manifest, indent=2) + '\n')
    matrix = {'format': 'c230241-unselected-fallback-matrix-v1',
              'case_id': CASE, 'manifest_sha256': sha(destination),
              'candidates': entries, 'lamp_target_held_fixed': True,
              'physical_visibility_verified': False}
    matrix_path = ROOT / 'native/fallback-matrix.json'
    matrix_path.write_text(json.dumps(matrix, indent=2) + '\n')
    return matrix


if __name__ == '__main__':
    result = build()
    print(json.dumps({'candidates': len(result['candidates']),
                      'manifest_sha256': result['manifest_sha256']}))
