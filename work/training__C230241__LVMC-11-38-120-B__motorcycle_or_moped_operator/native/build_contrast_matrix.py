"""Build an unselected Position-only front-headlamp contrast and fallbacks.

The requested lamp command is an intervention, not a measured visibility claim.
The rear position-light request, capture plan and controller remain fixed.
"""
import copy
import hashlib
import json
from pathlib import Path

from contrast_runner import check


CASE = Path(__file__).resolve().parents[1]
HERE = Path(__file__).resolve().parent
CASE_ID = CASE.name + '__contrast'
CANDIDATES = ('primary', 'fallback1', 'fallback2', 'fallback3')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def changed(left, right, prefix=''):
    if isinstance(left, dict) and isinstance(right, dict):
        return {entry for key in left.keys() | right.keys()
                for entry in changed(left.get(key), right.get(key), prefix + '/' + key)}
    if isinstance(left, list) and isinstance(right, list):
        if len(left) != len(right):
            return {prefix}
        return {entry for i, (a, b) in enumerate(zip(left, right))
                for entry in changed(a, b, prefix + '/' + str(i))}
    return set() if left == right else {prefix}


def build():
    reference_path = CASE / 'draft-primary/reference/primary/construction.json'
    reference = json.loads(reference_path.read_text())
    reference_config = json.loads(next(item['content'] for item in reference['files']
                                       if item['path'] == 'config.json'))
    runner = (HERE / 'contrast_runner.py').read_text()
    assert reference_config['requested_light_state'] == 'LowBeam|Position'
    base = copy.deepcopy(reference_config)
    base.update({'case_id': CASE_ID, 'selected_case_id': CASE_ID,
                 'case': 'contrast', 'requested_light_state': 'Position'})
    assert check(base)['frames'] == 600
    allowed = {
        'primary': set(),
        'fallback1': {'/candidate_id', '/spawn_point_index', '/vendor_spawn_point_index'},
        'fallback2': {'/candidate_id', '/cameras/0/location_xyz_m/0'},
        'fallback3': {'/candidate_id', '/cameras/1/fov_deg'},
    }
    entries = []
    for candidate in CANDIDATES:
        config = copy.deepcopy(base)
        config['candidate_id'] = candidate
        if candidate == 'fallback1':
            config['spawn_point_index'] = 2
            config['vendor_spawn_point_index'] = 3
        elif candidate == 'fallback2':
            config['cameras'][0]['location_xyz_m'][0] = -8
        elif candidate == 'fallback3':
            config['cameras'][1]['fov_deg'] = 80
        assert changed(base, config) == allowed[candidate]
        assert check(config)['candidate_id'] == candidate
        construction = copy.deepcopy(reference)
        construction['case_id'] = CASE_ID
        construction['files'] = [
            dict(item, content=runner) if item['path'] == 'runner.py' else
            dict(item, content=json.dumps(config, indent=2) + '\n')
            if item['path'] == 'config.json' else item
            for item in construction['files']]
        path = CASE / 'draft-contrast/contrast' / candidate / 'construction.json'
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(construction, indent=2) + '\n')
        entries.append({'id': candidate, 'construction': str(path.relative_to(CASE)),
                        'construction_sha256': sha(path),
                        'changed_config_paths': sorted(allowed[candidate])})
    manifest = {
        'assignment_id': CASE.name,
        'format': 'worker-unselected-draft-construction-manifest-v1',
        'status': 'draft_not_selected',
        'cases': [{
            'case_id': CASE_ID,
            'construction': entries[0]['construction'],
            'construction_sha256': entries[0]['construction_sha256'],
            'candidates': [{key: row[key] for key in
                            ('id', 'construction', 'construction_sha256')}
                           for row in entries[1:]],
            'candidate_risk': {
                'status': 'physical',
                'reason': 'Position-only request may not yield the intended front/rear lamp output; original camera and calibrated range review required.'}}],
        'original_native_observed': False,
        'delivery_ready': False,
    }
    manifest_path = CASE / 'draft-contrast-manifest.json'
    manifest_path.write_text(json.dumps(manifest, indent=2) + '\n')
    matrix = {
        'format': 'c230241-unselected-contrast-matrix-v1',
        'case_id': CASE_ID,
        'reference_primary_sha256': sha(reference_path),
        'manifest_sha256': sha(manifest_path),
        'contrast_runner_sha256': sha(HERE / 'contrast_runner.py'),
        'candidates': entries,
        'front_request': 'Position',
        'rear_position_request_held_fixed': True,
        'physical_visibility_verified': False,
    }
    matrix_path = HERE / 'contrast-matrix.json'
    matrix_path.write_text(json.dumps(matrix, indent=2) + '\n')
    print(json.dumps({'candidates': len(entries),
                      'matrix_sha256': sha(matrix_path),
                      'manifest_sha256': sha(manifest_path)}))


if __name__ == '__main__':
    build()
