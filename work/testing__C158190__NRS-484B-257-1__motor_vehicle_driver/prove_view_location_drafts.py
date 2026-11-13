"""Bind the three unselected view-location drafts to returned offline receipts."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]

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
    compat_manifest = json.loads((ROOT / 'view-location-compatibility-manifest.json').read_text())
    rows = manifest['cases']
    assert [row['occluder_center_y_m'] for row in rows] == [12., 15., 18.]
    assert [row['case_id'] for row in compat_manifest['cases']] == [row['case_id'] for row in rows]
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
    for row, compat_entry in zip(rows, compat_manifest['cases']):
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
        assert 'actor.bounding_box.get_world_vertices(actor.get_transform())' in files['view_location_world_setup.py']
        assert 'Native roadside obstruction cannot intersect authored eye ray' in files['view_location_world_setup.py']
        assert 'test_short_body_rejected_and_destroyed' in files['tests/test_view_location_world_setup.py']
        assert 'world.cast_ray(eye, target)' in files['yield_capture_sources.py']
        log = ROOT / f'cases/view_location_y{center}/offline.log'
        receipt = json.loads(log.read_text())
        assert receipt['case_id'] == row['case_id']
        assert receipt['offline_passed'] is True and receipt['simulation_started'] is False
        runtime_log = Path(receipt['log'])
        assert runtime_log.is_file() and 'OK' in runtime_log.read_text()
        assert compat_entry['construction_sha256'] == row['construction_sha256']
        recipe_path = REPO / compat_entry['fixture_recipe']
        recipe = json.loads(recipe_path.read_text())
        assert len(recipe['sources']) == 16
        for source in recipe['sources']:
            assert sha(REPO / source['source']) == source['sha256']
        assert sha(REPO / recipe['generator']['source']) == recipe['generator']['sha256']
        case_dir = ROOT / f'cases/view_location_y{center}'
        positive = json.loads((case_dir / 'compatibility.json').read_text())
        saved = json.loads((case_dir / 'saved-processing.json').read_text())
        assert positive['case_id'] == row['case_id'] and positive['candidate_id'] == 'primary'
        assert positive['passed'] is True
        assert positive['construction_sha256'] == row['construction_sha256']
        assert positive['fixture_recipe_sha256'] == sha(recipe_path)
        assert {'selected_measurements', 'negative_case_source', 'lean_decoder',
                'final_decode', 'four_camera_sources'} <= set(positive['checks'])
        assert positive['negative_removed'] == 'visibility_rays.jsonl'
        assert saved['case_id'] == row['case_id'] and saved['passed'] is True
        assert saved['recorded_only'] is True and saved['originals_preserved'] is True
        assert saved['physical_acceptance_claimed'] is False
        assert saved['legal_acceptance_claimed'] is False
        assert saved['native_revision']['construction_sha256'] == row['construction_sha256']
        assert saved['original_source_hashes']['visibility_rays.jsonl'] == positive['fixture_manifest']['visibility_rays.jsonl']
        context_source = next(item for item in recipe['sources'] if item['path'] == 'road_context.json')
        context = json.loads((REPO / context_source['source']).read_text())
        assert context['view_occluder']['native_location_m'] == [-4., float(center), 0.]
        assert context['view_occluder']['source_kind'] == 'synthetic_diagnostic'
        rays_source = next(item for item in recipe['sources'] if item['path'] == 'visibility_rays.jsonl')
        rays = [json.loads(line) for line in (REPO / rays_source['source']).read_text().splitlines()]
        assert len(rays) == 2 and all(ray['target_m'] == [1.8, 20., 1.5] for ray in rays)
        assert all(ray['ego_distance_to_junction_m'] == ray['distance_to_intersection_m'] for ray in rays)
        sources.append({'case_id': row['case_id'], 'construction_sha256': sha(path),
                        'offline_receipt_sha256': sha(log), 'center_y_m': center,
                        'recipe_sha256': sha(recipe_path),
                        'compatibility_sha256': sha(case_dir / 'compatibility.json'),
                        'saved_processing_sha256': sha(case_dir / 'saved-processing.json')})
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
