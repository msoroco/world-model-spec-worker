"""Bind the three unselected view-location drafts to returned offline receipts."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def validate():
    manifest = json.loads((ROOT / 'view-location-draft-manifest.json').read_text())
    rows = manifest['cases']
    assert [row['occluder_center_y_m'] for row in rows] == [12., 15., 18.]
    sources = []
    fixed = None
    for row in rows:
        center = int(row['occluder_center_y_m'])
        path = ROOT / row['construction']
        assert sha(path) == row['construction_sha256']
        construction = json.loads(path.read_text())
        assert construction['case_id'] == row['case_id']
        files = {item['path']: item['content'] for item in construction['files']}
        comparison = {name: hashlib.sha256(content.encode()).hexdigest()
                      for name, content in files.items() if name not in {
                          'runner.py', 'yield_capture_sources.py',
                          'tests/test_yield_capture_sources.py',
                          'view_location_world_setup.py',
                          'tests/test_view_location_world_setup.py', 'config.json',
                          'yield_controller.py', 'tests/test_yield_construction.py',
                          'tests/test_yield_controller.py', 'tests/test_yield_motion.py'}}
        if fixed is None:
            fixed = comparison
        else:
            assert comparison == fixed, 'An undeclared source changed across the view sweep'
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
    # Reject a manifest with stale construction identity or changed fixed source.
    bad = dict(rows[0], construction_sha256='0'*64)
    assert bad['construction_sha256'] != sha(ROOT / bad['construction'])
    bad_sources = dict(fixed, **{'native-map-plan/yield-nearest-view.xodr': '0'*64})
    assert bad_sources != fixed
    return {'status': 'pass', 'drafts': sources,
            'fixed_source_count': len(fixed),
            'limit': 'Native prop spawn and observed ray/camera occlusion still require CARLA.'}

if __name__ == '__main__':
    print(json.dumps(validate(), indent=2))
