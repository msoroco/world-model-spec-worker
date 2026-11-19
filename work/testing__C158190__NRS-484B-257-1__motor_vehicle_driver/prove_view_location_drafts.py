"""Bind the three unselected view-location drafts to returned offline receipts."""
import hashlib
import json
import copy
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
        # The shared controller enumerates all three exact view case IDs.
        # Its bytes must match across the comparison, including that list.
        text = content if name == 'yield_controller.py' else content.replace(case_suffix, '__VIEW_CASE__')
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

def require_returned_proof(entry, offline, positive, negative, saved):
    if entry['offline_log'] != offline or entry['compatibility_receipt'] != positive:
        raise ValueError('Returned view fallback differs from current replay')
    if entry['negative_log'] != negative or entry['saved_receipt'] != saved:
        raise ValueError('Returned view fallback differs from current negative or saved proof')

def compare_diagnostic_sources(baseline, candidate, case_id, center):
    """Permit only the authored case ID and roadside center in original-source fixtures."""
    baseline_sources = {item['path']: item for item in baseline['sources']}
    sources = {item['path']: item for item in candidate['sources']}
    if len(baseline_sources) != len(baseline['sources']) or len(sources) != len(candidate['sources']):
        raise ValueError('Duplicate diagnostic source path')
    if set(sources) != set(baseline_sources):
        raise ValueError('Diagnostic source inventory changed')
    variable = {'road_context.json', 'capture/manifest.json'}
    for name in sources.keys() - variable:
        if sources[name] != baseline_sources[name]:
            raise ValueError('Undeclared diagnostic source changed: ' + name)
    if candidate['generator']['sha256'] != baseline['generator']['sha256']:
        raise ValueError('Diagnostic generator changed')
    context = json.loads((REPO / sources['road_context.json']['source']).read_text())
    original = json.loads((REPO / baseline_sources['road_context.json']['source']).read_text())
    expected_context = copy.deepcopy(original)
    expected_context['view_occluder']['actor_id'] = 900 + center
    expected_context['view_occluder']['native_location_m'][1] = float(center)
    if context != expected_context:
        raise ValueError('Road context changed beyond occluder center')
    capture = json.loads((REPO / sources['capture/manifest.json']['source']).read_text())
    original_capture = json.loads((REPO / baseline_sources['capture/manifest.json']['source']).read_text())
    expected_capture = dict(original_capture, case_id=case_id)
    if capture != expected_capture:
        raise ValueError('Capture manifest changed beyond case identity')
    return len(sources) - len(variable)


def validate_view_fallbacks(compat_manifest, center):
    """Bind each distinct response to its exact CPU construction and replay."""
    entry = next(row for row in compat_manifest['cases']
                 if row['case_id'].endswith(f'occluder_y{center}'))
    primary = {item['path']: item['content'] for item in
               json.loads((ROOT / entry['construction']).read_text())['files']}
    expected_changes = {
        'fallback1': {'runner.py', 'tests/test_view_location_world_setup.py'},
        'fallback2': {'runner.py'},
        'fallback3': {'yield_construction.py', 'tests/test_yield_construction.py'},
    }
    candidates = entry.get('candidates', [])
    assert [row['id'] for row in candidates] == list(expected_changes)
    assert len({json.dumps(row['trigger'], sort_keys=True) for row in candidates}) == 3
    source_manifest = json.loads((ROOT / 'view-location-fallback1-source-manifest.json').read_text())
    source_entry = next(row for row in source_manifest['cases'] if row['case_id'] == entry['case_id'])
    bundle_path = ROOT / f'current-view-y{center}-fallback-proofs.json'
    bundle = json.loads(bundle_path.read_text())
    assert bundle['passed'] is True and bundle['case_id'] == entry['case_id']
    assert bundle['candidate_count'] == 3 and bundle['native_physical_acceptance'] is False
    assert [row['candidate_id'] for row in bundle['candidates']] == list(expected_changes)
    source_recipe = json.loads((REPO / source_entry['fixture_recipe']).read_text())
    primary_recipe = json.loads((REPO / entry['fixture_recipe']).read_text())
    source_map = {item['path']: item for item in source_recipe['sources']}
    primary_map = {item['path']: item for item in primary_recipe['sources']}
    assert set(source_map) == set(primary_map)
    assert all(source_map[name] == primary_map[name] for name in source_map if name != 'road_context.json')
    context = json.loads((REPO / source_map['road_context.json']['source']).read_text())
    original = json.loads((REPO / primary_map['road_context.json']['source']).read_text())
    original['view_occluder']['native_location_m'][1] = center - .5
    assert context == original
    assert sha(REPO / source_map['road_context.json']['source']) == source_map['road_context.json']['sha256']
    out = []
    for candidate in candidates:
        ident = candidate['id']
        construction = ROOT / candidate['construction']
        assert sha(construction) == candidate['construction_sha256']
        files = {item['path']: item['content'] for item in
                 json.loads(construction.read_text())['files']}
        assert set(files) == set(primary)
        assert {name for name in files if files[name] != primary[name]} == expected_changes[ident]
        if ident == 'fallback1':
            assert f'view_occluder(world, center_y={center - .5:.1f})' in files['runner.py']
            assert f'{center:.1f}' not in files['tests/test_view_location_world_setup.py']
            source_candidate = source_entry['candidates'][0]
            assert source_candidate['construction_sha256'] == candidate['construction_sha256']
            assert source_map['road_context.json']['sha256'] != primary_map['road_context.json']['sha256']
            recipe = source_entry['fixture_recipe']
        elif ident == 'fallback2':
            assert "'reference_corner': pose(23, -28, 18, 135, -27)" in files['runner.py']
            recipe = entry['fixture_recipe']
        else:
            assert 'EGO_POINT = opendrive_to_carla(-70.0, -1.8)' in files['yield_construction.py']
            recipe = entry['fixture_recipe']
        local = REPO / f'.runtime-work/view-y{center}-{ident}-current'
        offline = local.with_name(local.name + '-offline') / 'offline.log'
        positive_path = local.with_name(local.name + '-compat') / 'compatibility.json'
        negative_path = local.with_name(local.name + '-compat') / 'negative-analysis.log'
        saved_path = local.with_name(local.name + '-saved') / 'v0001/processing.json'
        assert 'OK' in offline.read_text()
        positive = json.loads(positive_path.read_text())
        saved = json.loads(saved_path.read_text())
        assert positive['case_id'] == entry['case_id'] and positive['candidate_id'] == ident
        assert positive['passed'] is True and positive['construction_sha256'] == candidate['construction_sha256']
        assert positive['fixture_recipe_sha256'] == sha(REPO / recipe)
        assert positive['negative_removed'] == 'visibility_rays.jsonl'
        assert {'negative_case_source', 'four_camera_sources', 'final_decode'} <= set(positive['checks'])
        assert saved['case_id'] == entry['case_id'] and saved['passed'] is True
        assert saved['recorded_only'] is True and saved['originals_preserved'] is True
        assert saved['physical_acceptance_claimed'] is False and saved['legal_acceptance_claimed'] is False
        assert saved['native_revision']['construction_sha256'] == candidate['construction_sha256']
        returned = next(row for row in bundle['candidates'] if row['candidate_id'] == ident)
        assert returned['construction_sha256'] == candidate['construction_sha256']
        assert returned['fixture_recipe_sha256'] == sha(REPO / recipe)
        assert returned['offline_log_sha256'] == sha(offline)
        assert returned['compatibility_receipt_sha256'] == sha(positive_path)
        assert returned['negative_log_sha256'] == sha(negative_path)
        assert returned['saved_receipt_sha256'] == sha(saved_path)
        require_returned_proof(returned, offline.read_text(), positive,
                               negative_path.read_text(), saved)
        changed = dict(returned, negative_log='changed evidence')
        try:
            require_returned_proof(changed, offline.read_text(), positive,
                                   negative_path.read_text(), saved)
        except ValueError:
            pass
        else:
            raise AssertionError('Changed returned negative proof escaped audit')
        out.append({'id': ident, 'construction_sha256': candidate['construction_sha256'],
                    'offline_log_sha256': sha(offline), 'compatibility_sha256': sha(positive_path),
                    'saved_processing_sha256': sha(saved_path),
                    'returned_bundle_sha256': sha(bundle_path)})
    return out


def validate_view_physical_fixtures(center):
    """Check classifier contrast and saved-processing lifecycle on CPU fixtures."""
    base = REPO / f'.runtime-work/c158190-view-y{center}-physical'
    statuses = {'complete_motion': 'met', 'incomplete_motion': 'not_met',
                'missing_evidence': 'unverified'}
    rows = []
    for kind, expected in statuses.items():
        path = base / f'{kind}.json'
        log = REPO / f'.runtime-work/c158190-view-y{center}-{kind}.log'
        assert log.is_file() and path.is_file()
        result = json.loads(path.read_text())
        assert result['physical_checks']['maneuver']['status'] == expected
        assert result['maneuver_completed'] is (expected == 'met')
        assert result['diagnostic_fixture'] is True
        assert result['physical_acceptance_claimed'] is False
        rows.append({'kind': kind, 'status': expected, 'result_sha256': sha(path),
                     'log_sha256': sha(log)})
    life_path = base / 'lifecycle.json'
    life_log = REPO / f'.runtime-work/c158190-view-y{center}-lifecycle.log'
    life = json.loads(life_path.read_text())
    assert life['events'] == ['capture_finished', 'encoders_closed',
                              'restoration_verified', 'native_exit',
                              'owner_released', 'saved_processing_started']
    assert life['diagnostic_fixture'] is True
    rows.append({'kind': 'lifecycle', 'result_sha256': sha(life_path),
                 'log_sha256': sha(life_log)})
    return rows

def validate():
    manifest = json.loads((ROOT / 'view-location-draft-manifest.json').read_text())
    compat_manifest = json.loads((ROOT / 'view-location-compatibility-manifest.json').read_text())
    rows = manifest['cases']
    assert [row['occluder_center_y_m'] for row in rows] == [12., 15., 18.]
    assert [row['case_id'] for row in compat_manifest['cases']] == [row['case_id'] for row in rows]
    plan = json.loads((ROOT / 'case-plan.json').read_text())
    comparisons = [row for row in plan['comparisons']
                   if row['comparison_id'] == 'same_approach_view_occluder_y12_y15_y18']
    assert len(comparisons) == 1
    assert comparisons[0]['case_ids'] == [row['case_id'] for row in rows]
    assert len(comparisons[0]['deliberate_differences']) == 1
    assert len(comparisons[0]['fixed_conditions']) == 3
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
    fixed_recipe = None
    fixed_diagnostic_source_count = None
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
        assert "'source_kind': 'original_native'" in files['view_location_world_setup.py']
        assert files['view_location_range_audit.py'] == (ROOT / 'view_location_range_audit.py').read_text()
        assert "audit_files(output / 'visibility_rays.jsonl'" in files['runner.py']
        assert "output / 'video_frames.jsonl'" in files['runner.py']
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
        if fixed_recipe is None:
            fixed_recipe = recipe
        fixed_count = compare_diagnostic_sources(fixed_recipe, recipe, row['case_id'], center)
        if fixed_diagnostic_source_count is None:
            fixed_diagnostic_source_count = fixed_count
        assert fixed_count == fixed_diagnostic_source_count
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
    changed_recipe = copy.deepcopy(fixed_recipe)
    next(item for item in changed_recipe['sources'] if item['path'] == 'road.xodr')['sha256'] = '0'*64
    try:
        compare_diagnostic_sources(fixed_recipe, changed_recipe, rows[0]['case_id'], 12)
    except ValueError as exc:
        assert 'Undeclared diagnostic source changed' in str(exc)
    else:
        raise AssertionError('Changed fixed diagnostic source escaped comparison audit')
    return {'status': 'pass', 'drafts': sources,
            'view_fallbacks': {str(center): validate_view_fallbacks(compat_manifest, center)
                               for center in (12, 15, 18)},
            'view_physical_fixtures': {str(center): validate_view_physical_fixtures(center)
                                       for center in (12, 15, 18)},
            'fixed_source_count': len(fixed),
            'fixed_diagnostic_source_count': fixed_diagnostic_source_count,
            'negative_diagnostic_change_rejected': True,
            'projected_ego_distance_to_junction_m': projected,
            'limit': 'Native prop spawn and observed ray/camera occlusion still require CARLA.'}

if __name__ == '__main__':
    print(json.dumps(validate(), indent=2))
