"""Build a separate vehicle-clearance turn from the proved indicator case.

The fixture changes an original-shaped body path. It does not establish that a
real vehicle would be affected or that the turn is reasonably safe.
"""
from hashlib import sha256
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ASSIGNMENT = ROOT.name
OLD = ASSIGNMENT + '__other_vehicle_signal_before_turn'
NEW = ASSIGNMENT + '__vehicle_clearance_near_before_turn'


def digest(path):
    return sha256(path.read_bytes()).hexdigest()


def put(path, value, compact=False):
    options = {'separators': (',', ':')} if compact else {'indent': 2}
    path.write_text(json.dumps(value, **options) + '\n', encoding='utf-8')
    return digest(path)


def build():
    base = json.loads((ROOT / 'vehicle-indicator-construction.json').read_text())
    case = json.loads(json.dumps(base).replace(OLD, NEW))
    files = {item['path']: item for item in case['files']}
    config = json.loads(files['config.json']['content'])
    config['engineering'].update(vehicle_along_m=5.0, vehicle_left_m=2.0)
    files['config.json']['content'] = json.dumps(config, indent=2) + '\n'
    runner = files['runner.py']['content']
    old_import = 'from turn_native_route import select_left_turn, route_targets, control_step'
    assert old_import in runner
    runner = runner.replace(old_import, old_import + ', participant_spawn_transform')
    old_spawn = "world.try_spawn_actor(library.find('vehicle.audi.tt'), scene['exit'].transform)"
    assert old_spawn in runner
    new_spawn = ("world.try_spawn_actor(library.find('vehicle.audi.tt'), "
                 "participant_spawn_transform(carla, scene['approach'][0], "
                 "along_m=engineering.get('vehicle_along_m', 5.0), "
                 "left_m=engineering.get('vehicle_left_m', 2.0)))")
    runner = runner.replace(old_spawn, new_spawn)
    old_knobs = "'target_speed_mps', 'speed_gain', 'overview_x_m'}"
    assert old_knobs in runner
    runner = runner.replace(old_knobs, "'target_speed_mps', 'speed_gain', 'overview_x_m', 'vehicle_along_m', 'vehicle_left_m'}")
    assert "if engineering.get('route_spacing_m'" in runner
    runner = runner.replace("if engineering.get('route_spacing_m'", 
        "for key, lower, upper in (('vehicle_along_m', 0.0, 30.0), ('vehicle_left_m', -25.0, 25.0)):\n"
        "        value = engineering.get(key, 5.0 if key == 'vehicle_along_m' else 2.0)\n"
        "        if isinstance(value, bool) or not isinstance(value, (int, float)) or not __import__('math').isfinite(value) or not lower <= value <= upper:\n"
        "            raise ValueError('Invalid affected-vehicle offset: ' + key)\n"
        "    if engineering.get('route_spacing_m'", 1)
    files['runner.py']['content'] = runner
    files['turn_native_route.py']['content'] = (ROOT / 'native_horn/turn_native_route.py').read_text()
    path = ROOT / 'vehicle-clearance-near-construction.json'
    construction_hash = put(path, case)

    diagnostic = json.loads((ROOT / 'vehicle-indicator-diagnostic.json').read_text())
    source_rows = [json.loads(line) for line in diagnostic['files']['participant_bodies.jsonl'].splitlines() if line]
    for row in source_rows:
        row['bodies']['affected_vehicle']['x_m'] = 2.0
        row['bodies']['affected_vehicle']['y_m'] = 2.0
    diagnostic['files']['participant_bodies.jsonl'] = ''.join(json.dumps(row) + '\n' for row in source_rows)
    for name, value in list(diagnostic['files'].items()):
        diagnostic['files'][name] = value.replace(OLD, NEW)
    diagnostic_path = ROOT / 'vehicle-clearance-near-diagnostic.json'
    diagnostic_hash = put(diagnostic_path, diagnostic, compact=True)
    recipe = json.loads((ROOT / 'vehicle-indicator-recipe.json').read_text())
    recipe = json.loads(json.dumps(recipe).replace('vehicle-indicator-diagnostic.json', diagnostic_path.name))
    for source in recipe['sources']:
        source['sha256'] = diagnostic_hash
    recipe['generator']['sha256'] = diagnostic_hash
    put(ROOT / 'vehicle-clearance-near-recipe.json', recipe)
    contract = json.loads((ROOT / 'vehicle-indicator-measurement-contract.json').read_text().replace(OLD, NEW))
    put(ROOT / 'vehicle-clearance-near-measurement-contract.json', contract)
    proposal_path = ROOT / 'proposals/cases.json'
    proposals = json.loads(proposal_path.read_text())
    if NEW not in {item['case_id'] for item in proposals['cases']}:
        source_proposal = next(item for item in proposals['cases'] if item['case_id'] == OLD)
        proposals['cases'].append(json.loads(json.dumps(source_proposal).replace(OLD, NEW)))
        put(proposal_path, proposals)

    manifest_path = ROOT / 'execution-manifest.json'
    manifest = json.loads(manifest_path.read_text())
    existing = {entry['case_id']: entry for entry in manifest['cases']}
    entry = existing.get(NEW, {})
    if entry.get('construction_sha256') != construction_hash:
        entry = {'case_id': NEW, 'kind': 'delivery',
                 'construction': path.name, 'construction_sha256': construction_hash,
                 'measurement_procedure': {'entrypoint': 'turn_finalizer.py'},
                 'measurement_contract': 'vehicle-clearance-near-measurement-contract.json',
                 'fixture_recipe': f'work/{ASSIGNMENT}/vehicle-clearance-near-recipe.json',
                 'candidate_risk': {'status': 'physical', 'reason':
                     'The affected vehicle may spawn outside the observed approach corridor or be occluded.'},
                 'candidates': []}
    source_entry = existing[OLD]
    known = {candidate['id']: candidate for candidate in entry['candidates']}
    for source_candidate in source_entry['candidates']:
        candidate_id = source_candidate['id']
        alternate = json.loads(json.dumps(case))
        alternate_files = {item['path']: item for item in alternate['files']}
        source_alternate = json.loads((ROOT / source_candidate['construction']).read_text())
        source_files = {item['path']: item for item in source_alternate['files']}
        source_config = json.loads(source_files['config.json']['content'])
        alternate_config = json.loads(alternate_files['config.json']['content'])
        alternate_config['engineering'].update(source_config['engineering'])
        alternate_files['config.json']['content'] = json.dumps(alternate_config, indent=2) + '\n'
        if candidate_id == 'fallback3':
            alternate_files['turn_camera_capture.py']['content'] = source_files['turn_camera_capture.py']['content']
        candidate_path = ROOT / f'vehicle-clearance-near-{candidate_id}-construction.json'
        candidate_hash = put(candidate_path, alternate)
        prior = known.get(candidate_id, {})
        if prior.get('construction_sha256') != candidate_hash:
            prior = {'id': candidate_id, 'construction': candidate_path.name,
                'construction_sha256': candidate_hash,
                'trigger': source_candidate['trigger'],
                'changed_knobs': source_candidate['changed_knobs']}
        known[candidate_id] = prior
    entry['candidates'] = [known[candidate['id']] for candidate in source_entry['candidates']]
    manifest['cases'] = [item for item in manifest['cases'] if item['case_id'] != NEW] + [entry]
    put(manifest_path, manifest)
    plan_path = ROOT / 'case-plan.json'
    plan = json.loads(plan_path.read_text())
    for disposition in plan['requirement_dispositions']:
        if disposition['status'] == 'selected_required' and NEW not in disposition['case_ids']:
            disposition['case_ids'].append(NEW)
    if NEW not in {item['case_id'] for item in plan['cases']}:
        plan['cases'].append({'case_id': NEW, 'target_law_id': 'NRS-484B-413-1',
            'gap_ids': ['turn-safety', 'signal-timing'],
            'construction_state': 'primary_construction_pending_cpu_proofs',
            'purpose': 'Measure original affected-vehicle clearance after approach-relative near placement while retaining the same turn and indicator protocol.',
            'physical_risk': {'risk': 'Native affected-vehicle spawn, clearance and camera visibility may fail',
                'trigger_source': 'original Native vehicle body and four camera streams',
                'trigger_metric': 'spawn success, sampled surface gap and image visibility',
                'failure_condition': 'missing actor, incomplete turn or absent vehicle pixels'}})
        plan['comparisons'].append({'comparison_id': 'vehicle_clearance_near',
            'case_ids': [OLD, NEW],
            'fixed_conditions': ['same selected turn, ordinary driver, vehicle, indicator protocol, 20 Hz duration and four camera plan'],
            'deliberate_differences': ['affected vehicle placement: exit waypoint versus approach-relative 5 m along and 2 m left']})
    put(plan_path, plan)
    return NEW, construction_hash, diagnostic_hash


if __name__ == '__main__':
    print(build())
