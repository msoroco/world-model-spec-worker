"""Stage an actual pedestrian participant in the backing comparison.

The textual diagnostic only checks source joins. Native pedestrian position and
visibility remain observations for the local run and independent review.
"""
from hashlib import sha256
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WORK = Path(__file__).resolve().parent
STAGE = ROOT / '.runtime-work/c110779-native-stage'
BASE = WORK.name + '__backing_clear_vehicle'
CASE = WORK.name + '__backing_pedestrian'


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, separators=(',', ':')) + '\n')
    return sha256(path.read_bytes()).hexdigest()


def patch_once(source, old, new):
    if source.count(old) != 1:
        raise ValueError('Pedestrian Native patch anchor differs: ' + old[:50])
    return source.replace(old, new)


def audit_pair(base, pedestrian):
    """Reject a changed fixed source or a pedestrian absent from original rows."""
    a, b = base['files'], pedestrian['files']
    if set(a) != set(b):
        raise ValueError('Pedestrian pair source inventory differs')
    for name in a:
        if name in ('capture/manifest.json', 'backing_context.json', 'backing_motion.jsonl'):
            continue
        if a[name] != b[name]:
            raise ValueError('Pedestrian pair changed fixed source: ' + name)
    left = [json.loads(row) for row in a['backing_motion.jsonl'].splitlines()]
    right = [json.loads(row) for row in b['backing_motion.jsonl'].splitlines()]
    if not left or len(left) != len(right):
        raise ValueError('Pedestrian pair frame inventory differs')
    left_context = json.loads(a['backing_context.json'])
    right_context = json.loads(b['backing_context.json'])
    if left_context['participants'] != {k: v for k, v in right_context['participants'].items() if k != '30'}:
        raise ValueError('Pedestrian pair changed fixed traffic context')
    if right_context['participants'].get('30', {}).get('kind') != 'pedestrian':
        raise ValueError('Pedestrian context missing')
    for first, second in zip(left, right):
        if first != {**second, 'participants': {k: v for k, v in second['participants'].items() if k != '30'}}:
            raise ValueError('Pedestrian pair changed fixed original motion')
        if '30' not in second['participants']:
            raise ValueError('Original pedestrian body missing')
    return {'format': 'worker-backing-pedestrian-comparison-audit',
            'passed': True, 'frames': len(left), 'fixed_vehicle_and_ego': True,
            'original_pedestrian_rows': len(right), 'physical_or_legal_claim': False}


def main():
    source = json.loads((WORK / 'diagnostic-first-primary.json').read_text())
    diagnostic = json.loads(json.dumps(source))
    files = diagnostic['files']
    capture = json.loads(files['capture/manifest.json'])
    capture['case_id'] = CASE
    files['capture/manifest.json'] = json.dumps(capture) + '\n'
    context = json.loads(files['backing_context.json'])
    context['participants']['30'] = {
        'kind': 'pedestrian',
        'position_motion_purpose_source': 'synthetic authored pedestrian position and motion; Native readback required',
        'highway_use_source': 'synthetic authored intersection crossing; Native map review required',
        'purpose': 'cross reviewed intersection on foot'}
    files['backing_context.json'] = json.dumps(context) + '\n'
    rows = [json.loads(row) for row in files['backing_motion.jsonl'].splitlines()]
    for index, row in enumerate(rows):
        row['participants']['30'] = {'x_m': 12.0, 'y_m': 3.0 - .15 * index,
                                     'body_radius_m': .35, 'speed_mps': .75}
    files['backing_motion.jsonl'] = ''.join(json.dumps(row) + '\n' for row in rows)
    audit = audit_pair(source, diagnostic)
    diagnostic_path = WORK / 'diagnostic-backing-pedestrian.json'
    diagnostic_sha = write(diagnostic_path, diagnostic)
    recipe_path = WORK / 'diagnostic-recipe-backing-pedestrian.json'
    write(recipe_path, {'format': 'worker-fixture-recipe',
        'sources': [{'path': 'diagnostic-input.json',
                     'source': str(diagnostic_path.relative_to(ROOT)), 'sha256': diagnostic_sha}],
        'generator': {'source': str(diagnostic_path.relative_to(ROOT)), 'sha256': diagnostic_sha}})

    manifest_path = STAGE / 'execution-manifest.json'
    manifest = json.loads(manifest_path.read_text())
    base_entry = next(item for item in manifest['cases'] if item['case_id'] == BASE)
    base_construction = json.loads((STAGE / base_entry['construction']).read_text())
    construction = json.loads(json.dumps(base_construction))
    construction['case_id'] = CASE
    construction['mechanisms'].append('Spawn a separately sourced Native walker, command crossing motion and record its original body and speed every frame')
    for item in construction['files']:
        if item['path'] == 'config.json':
            config = json.loads(item['content'])
            config['selected_case_id'] = CASE
            config['supported_case_ids'] = [CASE]
            config['case']['case_id'] = CASE
            config['pedestrian_speed_mps'] = .75
            item['content'] = json.dumps(config, indent=2) + '\n'
        elif item['path'] == 'runner.py':
            runner = item['content']
            runner = patch_once(runner, "'backing_near_vehicle'}", "'backing_near_vehicle','backing_pedestrian'}")
            runner = patch_once(runner, "if config.get('other_throttle',.15) not in (.15,.25):",
                "if config.get('pedestrian_speed_mps',.75) not in (.5,.75,1.0):\n"
                "        raise ValueError('Unsupported pedestrian crossing speed')\n"
                "    if config.get('other_throttle',.15) not in (.15,.25):")
            runner = patch_once(runner,
                "for name in CAMERAS:sinks[name]=LosslessSourceSink(output,name)",
                "pedestrian_xy=source.get('pedestrian_xy')\n"
                "        if (not isinstance(pedestrian_xy,list) or len(pedestrian_xy)!=2 or\n"
                "                not source.get('pedestrian_purpose') or\n"
                "                not source.get('pedestrian_evidence_reference') or\n"
                "                not all(__import__('math').isfinite(float(v)) for v in pedestrian_xy)):\n"
                "            raise ValueError('Reviewed pedestrian crossing source is absent')\n"
                "        from backing_corridor import _inside\n"
                "        if not _inside(tuple(pedestrian_xy),source['intersection_polygon_xy']):\n"
                "            raise ValueError('Reviewed pedestrian is outside intersection')\n"
                "        pedestrian_location=carla.Location(x=pedestrian_xy[0],y=pedestrian_xy[1],z=.5)\n"
                "        pedestrian_transform=carla.Transform(pedestrian_location)\n"
                "        pedestrian=world.try_spawn_actor(world.get_blueprint_library().find('walker.pedestrian.0001'),pedestrian_transform)\n"
                "        if pedestrian is None:raise ValueError('Native pedestrian spawn failed')\n"
                "        owned.append(pedestrian)\n"
                "        for name in CAMERAS:sinks[name]=LosslessSourceSink(output,name)")
            runner = patch_once(runner,
                "recorder=BackingSourceRecorder(output,ego,[other],context)",
                "context['participants'][str(pedestrian.id)]={'kind':'pedestrian',\n"
                "            'position_motion_purpose_source':'Reviewed pedestrian crossing source and original Native transform/velocity',\n"
                "            'highway_use_source':'Reviewed intersection polygon and original Native location',\n"
                "            'purpose':source['pedestrian_purpose'],\n"
                "            'evidence_reference':source['pedestrian_evidence_reference']}\n"
                "        recorder=BackingSourceRecorder(output,ego,[other,pedestrian],context)")
            runner = patch_once(runner,
                "other.apply_control(carla.VehicleControl(throttle=config.get('other_throttle',.15),steer=0))",
                "other.apply_control(carla.VehicleControl(throttle=config.get('other_throttle',.15),steer=0))\n"
                "            pedestrian.apply_control(carla.WalkerControl(direction=carla.Vector3D(0,-1,0),\n"
                "                speed=config.get('pedestrian_speed_mps',.75)))")
            item['content'] = runner

    contract = json.loads((STAGE / base_entry['measurement_contract']).read_text())
    contract['case_id'] = CASE
    contract_path = STAGE / 'measurement-backing-pedestrian.json'
    write(contract_path, contract)
    entry = {key: json.loads(json.dumps(value)) for key, value in base_entry.items() if key != 'candidates'}
    entry.update(case_id=CASE, measurement_contract=contract_path.name,
                 fixture_recipe=str(recipe_path.relative_to(ROOT)),
                 candidate_risk={'status': 'physical', 'reason': 'Native walker spawning, crossing and four-camera visibility require original readback.'},
                 candidates=[])
    for candidate in ('primary', 'fallback1', 'fallback2', 'fallback3'):
        alternate = json.loads(json.dumps(construction))
        config_item = next(x for x in alternate['files'] if x['path'] == 'config.json')
        config = json.loads(config_item['content'])
        if candidate == 'fallback1':
            config['pedestrian_speed_mps'] = .5
        elif candidate == 'fallback2':
            config['pedestrian_speed_mps'] = 1.0
        elif candidate == 'fallback3':
            config['overview_height_delta_m'] = 2
        config_item['content'] = json.dumps(config, indent=2) + '\n'
        path = STAGE / f'construction-backing-pedestrian-{candidate}.json'
        digest = write(path, alternate)
        if candidate == 'primary':
            entry.update(construction=path.name, construction_sha256=digest)
        else:
            metrics = {
                'fallback1': ('original pedestrian position and velocity', 'crossing displacement', 'pedestrian exits crossing before reviewed backing window'),
                'fallback2': ('original pedestrian position and velocity', 'crossing displacement', 'pedestrian fails to enter backing corridor during reviewed window'),
                'fallback3': ('original overview camera frames and pedestrian position', 'pedestrian pixel visibility', 'walker leaves overview field of view')}
            source_name, metric, failure = metrics[candidate]
            knob = 'overview_height_delta_m' if candidate == 'fallback3' else 'pedestrian_speed_mps'
            entry['candidates'].append({'id': candidate, 'construction': path.name,
                'construction_sha256': digest,
                'trigger': {'source': source_name, 'metric': metric, 'failure_condition': failure},
                'changed_knobs': [f'{knob}: {config[knob]}']})
    manifest['cases'] = [item for item in manifest['cases'] if item['case_id'] != CASE] + [entry]
    write(manifest_path, manifest)
    plan_path = STAGE / 'case-plan.json'
    plan = json.loads(plan_path.read_text())
    for disposition in plan['requirement_dispositions']:
        disposition['case_ids'] = sorted(set(disposition['case_ids']) | {CASE})
    for planned in plan['cases']:
        if planned['case_id'] == CASE:
            planned['construction_status'] = 'staged_primary_and_fallbacks'
    write(plan_path, plan)
    proposal_path = STAGE / 'proposals/cases.json'
    if proposal_path.exists():
        proposal = json.loads(proposal_path.read_text())
        proposal['cases'] = [item for item in proposal['cases'] if item['case_id'] != CASE]
        basis = next(item for item in proposal['cases'] if item['case_id'] == BASE)
        pedestrian_case = json.loads(json.dumps(basis))
        pedestrian_case.update(case_id=CASE,
            rationale='Same backing and vehicle traffic with an additionally sourced Native pedestrian crossing; observed motion is measured from originals',
            variable_assignments={'pedestrian_crossing': True})
        proposal['cases'].append(pedestrian_case)
        write(proposal_path, proposal)
    return {'case_id': CASE, 'diagnostic_sha256': diagnostic_sha,
            'candidate_hashes': [entry['construction_sha256']] + [x['construction_sha256'] for x in entry['candidates']],
            'comparison_audit': audit}


if __name__ == '__main__':
    print(json.dumps(main(), indent=2))
