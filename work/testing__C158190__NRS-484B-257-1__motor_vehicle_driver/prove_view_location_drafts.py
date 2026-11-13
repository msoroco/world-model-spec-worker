"""Bind the three unselected view-location drafts to returned offline receipts."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def canonical_sources(row, files):
    """Erase only the declared case identity and roadside center difference."""
    case_suffix = row['case_id'].split('__')[-1]
    center = row['occluder_center_y_m']
    normalized = {}
    for name, content in files.items():
        text = content.replace(case_suffix, '__VIEW_CASE__')
        if name == 'runner.py':
            anchor = f'view_occluder(world, center_y={center:.1f})'
            assert text.count(anchor) == 1
            text = text.replace(anchor, 'view_occluder(world, center_y=__CENTER__)')
        if name == 'tests/test_view_location_world_setup.py':
            assert text.count(f'{center:.1f}') >= 1
            text = text.replace(f'{center:.1f}', '__CENTER__')
        normalized[name] = hashlib.sha256(text.encode()).hexdigest()
    return normalized

def require_same_sources(expected, actual):
    if expected != actual:
        raise ValueError('Undeclared embedded source change in view-location comparison')

def validate():
    manifest = json.loads((ROOT / 'view-location-draft-manifest.json').read_text())
    rows = manifest['cases']
    assert [row['occluder_center_y_m'] for row in rows] == [12., 15., 18.]
    axis = manifest['view_axis']
    assert axis['world_setup_parameter'] == 'roadside_occluder_center_y_m'
    assert axis['sampled_center_y_m'] == [12., 15., 18.]
    projected = []
    for center_y in axis['sampled_center_y_m']:
        fraction = (center_y - 1.8) / (20. - 1.8)
        ego_x = (-4. - fraction * 1.8) / (1. - fraction)
        projected.append(-8. - ego_x)
    assert all(abs(a-b) < 1e-9 for a, b in zip(
        projected, axis['projected_ego_distance_to_junction_m']))
    assert 0 < projected[0] < projected[1] < projected[2] < 52
    sources = []
    fixed = None
    for row in rows:
        center = int(row['occluder_center_y_m'])
        path = ROOT / row['construction']
        assert sha(path) == row['construction_sha256']
        construction = json.loads(path.read_text())
        assert construction['case_id'] == row['case_id']
        files = {item['path']: item['content'] for item in construction['files']}
        comparison = canonical_sources(row, files)
        if fixed is None:
            fixed = comparison
        else:
            require_same_sources(fixed, comparison)
        assert 'view_occluder(world, center_y=' + f'{center:.1f}' in files['runner.py']
        assert 'view_occluder' in files['runner.py']
        assert "'view_occluder': obstruction" in files['runner.py']
        assert 'TARGET_XY = (1.8, 20.0)' in files['yield_capture_sources.py']
        assert "'ego_distance_to_junction_m': float(distance)" in files['yield_capture_sources.py']
        assert 'world.try_spawn_actor(blueprint, pose)' in files['view_location_world_setup.py']
        assert 'world.cast_ray(eye, target)' in files['yield_capture_sources.py']
        log = ROOT / f'cases/view_location_y{center}/offline.log'
        receipt = json.loads(log.read_text())
        assert receipt['case_id'] == row['case_id']
        assert receipt['offline_passed'] is True and receipt['simulation_started'] is False
        runtime_log = Path(receipt['log'])
        assert runtime_log.is_file() and 'OK' in runtime_log.read_text()
        sources.append({'case_id': row['case_id'], 'construction_sha256': sha(path),
                        'offline_receipt_sha256': sha(log), 'center_y_m': center})
    assert len({s['construction_sha256'] for s in sources}) == 3
    # Exercise actual audit rejection for changed construction identity and map.
    bad = dict(rows[0], construction_sha256='0'*64)
    assert bad['construction_sha256'] != sha(ROOT / bad['construction'])
    bad_sources = dict(fixed, **{'native-map-plan/yield-nearest-view.xodr': '0'*64})
    try:
        require_same_sources(fixed, bad_sources)
    except ValueError:
        pass
    else:
        raise AssertionError('Changed fixed road escaped comparison audit')
    return {'status': 'pass', 'drafts': sources,
            'fixed_source_count': len(fixed),
            'projected_ego_distance_to_junction_m': projected,
            'limit': 'Native prop spawn and observed ray/camera occlusion still require CARLA.'}

if __name__ == '__main__':
    print(json.dumps(validate(), indent=2))
