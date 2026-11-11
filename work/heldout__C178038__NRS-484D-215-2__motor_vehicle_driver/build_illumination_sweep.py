"""Materialize frozen low-beam illumination sweep points and CPU recipes."""

from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path

from native_headlamp_probe import SWEEP_CASES, check_config

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
ASSIGNMENT = HERE.name
OUT = HERE / 'sweep-probes'


def digest(path):
    return sha256(path.read_bytes()).hexdigest()


def write(path, value, compact=False):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, separators=(',', ':') if compact else None,
                               indent=None if compact else 2) + '\n')


def lines(rows):
    return ''.join(json.dumps(row, separators=(',', ':')) + '\n' for row in rows)


def build():
    semantic = json.loads((HERE / 'proposals/cases.json').read_text())
    points = {c['case_id']: c for c in semantic['cases'] if c.get('target_type') == 'judgment_sweep'}
    assert set(points) == set(SWEEP_CASES)
    manifest_path = HERE / 'execution-manifest.json'
    manifest = json.loads(manifest_path.read_text())
    manifest['cases'] = [e for e in manifest['cases'] if e['case_id'] not in SWEEP_CASES]
    model = next(e for e in manifest['cases'] if e['case_id'].endswith('__night_299_other'))
    model_construction = json.loads((HERE / model['construction']).read_text())
    model_spec = json.loads((HERE / 'night-probes/night_299_other-diagnostic-input.json').read_text())
    model_config = json.loads((HERE / 'night-probes/night_299_other-config.json').read_text())
    model_contract = json.loads((HERE / model['measurement_contract']).read_text())
    current_runner = (HERE / 'native_headlamp_probe.py').read_text()
    current_finalizer = (HERE / 'headlamp_finalizer.py').read_text()

    # Every inline bundle carries the exact current runner and finalizer. Preserve
    # each fallback's single physical repair while rebinding the shared source.
    for entry in manifest['cases']:
        for selected in [entry, *entry['candidates']]:
            path = HERE / selected['construction']
            construction = json.loads(path.read_text())
            for file in construction['files']:
                if file['path'] in ('native_headlamp_probe.py', 'runner.py'):
                    content = current_runner
                    if selected is not entry:
                        if selected['id'] == 'fallback1':
                            content = content.replace(
                                "select_follow_route(world.get_map(), target_gap_ft=config['requested_gap_ft'])",
                                "select_follow_route(world.get_map(), target_gap_ft=config['requested_gap_ft'], step_m=1.25)")
                            content = content.replace(
                                "select_follow_route(world.get_map(), target_gap_ft=config['requested_gap_ft'], surface='shoulder')",
                                "select_follow_route(world.get_map(), target_gap_ft=config['requested_gap_ft'], surface='shoulder', step_m=1.25)")
                        elif selected['id'] == 'fallback2':
                            content = content.replace('def _command(actor, target, speed=6):',
                                                      'def _command(actor, target, speed=5):')
                    file['content'] = content
                elif file['path'] == 'headlamp_finalizer.py':
                    file['content'] = current_finalizer
            write(path, construction)
            selected['construction_sha256'] = digest(path)
            selected.pop('offline', None)
            selected.pop('compatibility', None)
        entry.pop('physical_preparation', None)
        entry.pop('delivery_acceptance', None)
        entry.pop('post_capture', None)

    plan_path = HERE / 'case-plan.json'
    plan = json.loads(plan_path.read_text())
    plan['cases'] = [c for c in plan['cases'] if c['case_id'] not in SWEEP_CASES]
    disposition = plan['requirement_dispositions'][0]
    disposition['case_ids'] = [case_id for case_id in disposition['case_ids']
                               if case_id not in SWEEP_CASES] + list(SWEEP_CASES)
    for case_id, (gap, uppermost) in SWEEP_CASES.items():
        suffix = case_id.removeprefix(ASSIGNMENT + '__')
        point = points[case_id]
        config = deepcopy(model_config)
        config.update(selected_case_id=case_id, requested_gap_ft=gap,
                      requested_uppermost_distribution=uppermost)
        config['case']['recording_description'] = point['recording_description']
        check_config(config)
        config_rel = f'sweep-probes/{suffix}-config.json'
        write(HERE / config_rel, config)
        construction = deepcopy(model_construction)
        construction['case_id'] = case_id
        construction['recording_description'] = point['recording_description']
        for file in construction['files']:
            if file['path'] == 'config.json':
                file['content'] = (HERE / config_rel).read_text()
            elif file['path'] in ('native_headlamp_probe.py', 'runner.py'):
                file['content'] = current_runner
            elif file['path'] == 'headlamp_finalizer.py':
                file['content'] = current_finalizer
        construction_rel = f'sweep-probes/{suffix}-construction.json'
        write(HERE / construction_rel, construction)
        entry = deepcopy(model)
        entry.update(case_id=case_id, construction=construction_rel,
                     construction_sha256=digest(HERE / construction_rel),
                     measurement_contract=f'sweep-probes/{suffix}-measurement-contract.json',
                     fixture_recipe=f'work/{ASSIGNMENT}/sweep-probes/{suffix}-diagnostic-recipe.json',
                     candidate_risk={'status': 'physical',
                                     'reason': 'Actual distance and illumination pixel reach can differ from the requested setpoint.'},
                     candidates=[], negative={'log': f'sweep-probes/{suffix}-compat-negative.log'})
        for field in ('offline', 'compatibility', 'physical_preparation',
                      'delivery_acceptance', 'post_capture'):
            entry.pop(field, None)
        for candidate in model['candidates']:
            variant = deepcopy(construction)
            ident = candidate['id']
            if ident == 'fallback1':
                target = "select_follow_route(world.get_map(), target_gap_ft=config['requested_gap_ft'])"
                replacement = target[:-1] + ', step_m=1.25)'
                filename = 'native_headlamp_probe.py'
            elif ident == 'fallback2':
                target = 'def _command(actor, target, speed=6):'
                replacement = 'def _command(actor, target, speed=5):'
                filename = 'native_headlamp_probe.py'
            else:
                target = '"overview": ((-32, 0, 10), (-4, 0, 0), (1920, 1080), 95)'
                replacement = '"overview": ((-36, 0, 12), (-4, 0, 0), (1920, 1080), 95)'
                filename = 'headlamp_camera.py'
            for file in variant['files']:
                if file['path'] == filename:
                    if target not in file['content']:
                        raise ValueError('Missing fallback source anchor ' + filename)
                    file['content'] = file['content'].replace(target, replacement)
                elif file['path'] == 'runner.py' and filename == 'native_headlamp_probe.py':
                    file['content'] = file['content'].replace(target, replacement)
            relative = f'sweep-probes/{suffix}-{ident}-construction.json'
            write(HERE / relative, variant)
            item = deepcopy(candidate)
            item.update(construction=relative, construction_sha256=digest(HERE / relative))
            item.pop('offline', None)
            item.pop('compatibility', None)
            item['trigger']['failure_condition'] = item['trigger']['failure_condition'].replace('299 ft', f'{gap} ft')
            entry['candidates'].append(item)
        spec = deepcopy(model_spec)
        files = spec['files']
        footprint = [json.loads(line) for line in files['following_footprints.jsonl'].splitlines()]
        delta = (gap - 299) * .3048
        for row in footprint:
            row['lead_corners_xy'] = [[x + delta, y] for x, y in row['lead_corners_xy']]
        files['following_footprints.jsonl'] = lines(footprint)
        for name in ('capture/manifest.json', 'fixture-provenance.json'):
            value = json.loads(files[name]); value['case_id'] = case_id
            files[name] = json.dumps(value, indent=2) + '\n'
        spec_rel = f'sweep-probes/{suffix}-diagnostic-input.json'
        write(HERE / spec_rel, spec, compact=True)
        source = f'work/{ASSIGNMENT}/{spec_rel}'
        write(HERE / f'sweep-probes/{suffix}-diagnostic-recipe.json',
              {'format': 'worker-fixture-recipe',
               'sources': [{'path': f'{suffix}-diagnostic-input.json',
                            'source': source, 'sha256': digest(HERE / spec_rel)}],
               'generator': {'source': source, 'sha256': digest(HERE / spec_rel)}})
        contract = deepcopy(model_contract); contract['case_id'] = case_id
        write(HERE / entry['measurement_contract'], contract)
        plan['cases'].append({'case_id': case_id,
                              'requirement': plan['requirement_dispositions'][0]['requirement'],
                              'requested_engineering_setup': f'Night traveled portion, {gap} ft, non-uppermost low-beam readback; safe-distance judgment unresolved',
                              'status': 'exact_cpu_construction_pending_proof',
                              'source_refs': plan['cases'][0]['source_refs']})
        manifest['cases'].append(entry)
    plan['comparisons'] = [c for c in plan['comparisons']
                           if c['comparison_id'] != 'illumination_gap_sweep']
    plan['comparisons'].append({
        'comparison_id': 'illumination_gap_sweep',
        'case_ids': list(SWEEP_CASES),
        'fixed_conditions': 'nighttime traveled roadway, same actors and non-uppermost low-beam readback',
        'deliberate_differences': 'frozen 150, 299 and 225 ft requested following setpoints; actual original-body gap measured separately',
        'status': 'source_bound_synthetic_software_pending_proof',
        'source_refs': plan['cases'][0]['source_refs']})
    write(plan_path, plan)
    write(manifest_path, manifest)


if __name__ == '__main__':
    build()
