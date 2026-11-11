"""Expand C136539's frozen interior-clearance points into exact CPU bundles."""

from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path

from exposure_case_setup import CASES, PREFIX, case_settings

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SWEEP = {name: value for name, value in CASES.items()
         if name.startswith('exposure_clearance_sweep-')}


def sha(path):
    return sha256(path.read_bytes()).hexdigest()


def write(path, value, compact=False):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, separators=(',', ':') if compact else None,
                               indent=None if compact else 2) + '\n')


def build():
    proposal = json.loads((HERE / 'proposals/cases.json').read_text())
    points = {case['case_id']: case for case in proposal['cases']
              if case.get('target_type') == 'judgment_sweep'}
    if set(points) != {PREFIX + suffix for suffix in SWEEP}:
        raise ValueError('Frozen sweep selection differs from Native settings')
    setup_source = (HERE / 'exposure_case_setup.py').read_text()
    finalizer_source = (HERE / 'endangerment_finalizer.py').read_text()
    # Rebind every existing inline source copy. Candidate-specific route,
    # lookahead and camera edits stay in their own files.
    for path in [HERE / 'construction.json', HERE / 'construction-probe.json',
                 *sorted((HERE / 'cases').glob('construction-*.json'))]:
        if not path.is_file():
            continue
        construction = json.loads(path.read_text())
        for item in construction.get('files', []):
            if item['path'] == 'exposure_case_setup.py':
                item['content'] = setup_source
            elif item['path'] == 'endangerment_finalizer.py':
                item['content'] = finalizer_source
        write(path, construction)
    for name in ('construction-cases-manifest.json', 'probe-compatibility-manifest.json',
                 'fallback-constructions-manifest.json', 'execution-manifest.json'):
        path = HERE / name
        manifest = json.loads(path.read_text())
        manifest['cases'] = [e for e in manifest['cases'] if e['case_id'] not in points]
        for entry in manifest['cases']:
            entry['construction_sha256'] = sha(HERE / entry['construction'])
            for candidate in entry.get('candidates', []):
                candidate['construction_sha256'] = sha(HERE / candidate['construction'])
                if 'offline' in candidate:
                    candidate['offline']['construction_sha256'] = candidate['construction_sha256']
            if 'offline' in entry:
                entry['offline']['construction_sha256'] = entry['construction_sha256']
        write(path, manifest)

    model_name = 'moderate_person_exposure'
    model = json.loads((HERE / f'cases/construction-{model_name}.json').read_text())
    model_fallbacks = json.loads((HERE / 'fallback-constructions-manifest.json').read_text())
    model_fallback_entry = next(e for e in model_fallbacks['cases']
                                if e['case_id'].endswith('__' + model_name))
    model_primary = json.loads((HERE / 'probe-compatibility-manifest.json').read_text())
    model_primary_entry = next(e for e in model_primary['cases']
                               if e['case_id'].endswith('__' + model_name))
    model_execution = json.loads((HERE / 'execution-manifest.json').read_text())
    model_execution_entry = next(e for e in model_execution['cases']
                                 if e['case_id'].endswith('__' + model_name))
    model_spec = json.loads((HERE / f'diagnostic-{model_name}.json').read_text())
    contract = json.loads((HERE / f'cases/measurement-contract-{model_name}.json').read_text())
    plan_path = HERE / 'case-plan.json'
    plan = json.loads(plan_path.read_text())
    plan['cases'] = [c for c in plan['cases'] if c['case_id'] not in points]
    disposition = plan['requirement_dispositions'][0]
    disposition['case_ids'] = [c for c in disposition['case_ids'] if c not in points]
    for suffix, (speed, kind, lateral) in SWEEP.items():
        case_id = PREFIX + suffix
        case = points[case_id]
        construction = deepcopy(model)
        construction['case_id'] = case_id
        construction['recording_description'] = case['recording_description']
        config = None
        for item in construction['files']:
            if item['path'] == 'config.json':
                config = json.loads(item['content'])
                config.update(selected_case_id=case_id, requested_speed_mps=speed,
                              exposed_kind=kind, outside_edge_m=lateral)
                config['case']['recording_description'] = case['recording_description']
                case_settings(config)
                item['content'] = json.dumps(config, indent=2) + '\n'
        if config is None:
            raise ValueError('Sweep construction lacks config')
        construction_rel = f'cases/construction-{suffix}.json'
        write(HERE / construction_rel, construction)
        write(HERE / f'cases/config-{suffix}.json', config)
        candidates = []
        for prior in model_fallback_entry['candidates']:
            ident = prior['id']
            variant = deepcopy(construction)
            source = json.loads((HERE / prior['construction']).read_text())
            for item in variant['files']:
                if item['path'] in ('native_exposure_cases.py', 'runner.py',
                                    'narrow_exposure_route.py', 'exposure_camera.py'):
                    candidate_file = next(f for f in source['files'] if f['path'] == item['path'])
                    item['content'] = candidate_file['content']
            relative = f'cases/construction-{suffix}-{ident}.json'
            write(HERE / relative, variant)
            candidate = deepcopy(prior)
            candidate.update(construction=relative, construction_sha256=sha(HERE / relative))
            candidate.pop('offline', None); candidate.pop('compatibility', None)
            candidates.append(candidate)
        spec = deepcopy(model_spec)
        files = spec['files']
        rows = [json.loads(line) for line in files['exposed_actor_footprints.jsonl'].splitlines()]
        shift = lateral - 0.4
        for row in rows:
            row['exposed_corners_xy'] = [[x, y + shift] for x, y in row['exposed_corners_xy']]
            row['exposed_id'] = 'fixture-' + suffix
        files['exposed_actor_footprints.jsonl'] = ''.join(
            json.dumps(row, separators=(',', ':')) + '\n' for row in rows)
        capture = json.loads(files['capture/manifest.json']); capture['case_id'] = case_id
        files['capture/manifest.json'] = json.dumps(capture, indent=2) + '\n'
        diagnostic_rel = f'diagnostic-{suffix}.json'
        write(HERE / diagnostic_rel, spec, compact=True)
        source = f'work/{HERE.name}/{diagnostic_rel}'
        recipe_rel = f'diagnostic-recipe-{suffix}.json'
        write(HERE / recipe_rel, {
            'format': 'worker-fixture-recipe',
            'sources': [{'path': 'diagnostic-input.json', 'source': source,
                         'sha256': sha(HERE / diagnostic_rel)}],
            'generator': {'source': source, 'sha256': sha(HERE / diagnostic_rel)}})
        exact_contract = deepcopy(contract); exact_contract['case_id'] = case_id
        contract_rel = f'cases/measurement-contract-{suffix}.json'
        write(HERE / contract_rel, exact_contract)
        common = deepcopy(model_primary_entry)
        common.update(case_id=case_id, construction=construction_rel,
                      construction_sha256=sha(HERE / construction_rel),
                      measurement_contract=contract_rel,
                      fixture_recipe=f'work/{HERE.name}/{recipe_rel}',
                      compatibility={'receipt': f'case-{suffix}-compatibility.json',
                                     'log': f'case-{suffix}-compat.log',
                                     'negative_log': f'case-{suffix}-negative.log'},
                      negative={'log': f'case-{suffix}-negative.log'})
        for manifest_name in ('probe-compatibility-manifest.json',
                              'fallback-constructions-manifest.json',
                              'execution-manifest.json'):
            path = HERE / manifest_name
            manifest = json.loads(path.read_text())
            entry = deepcopy(common)
            if manifest_name != 'probe-compatibility-manifest.json':
                entry['candidate_risk'] = deepcopy(model_fallback_entry['candidate_risk'])
                entry['candidates'] = deepcopy(candidates)
            if manifest_name == 'execution-manifest.json':
                entry['kind'] = 'delivery'
                entry['native_handoff'] = deepcopy(model_execution_entry['native_handoff'])
            manifest['cases'].append(entry)
            write(path, manifest)
        plan['cases'].append({'case_id': case_id,
                              'requirement': plan['cases'][0]['requirement'],
                              'requested_engineering_setup': f'5 m/s requested pedestrian passage at {lateral} m exterior placement, 10 m downroute',
                              'status': 'exact_sweep_construction_pending_cpu_proofs',
                              'source_refs': plan['cases'][0]['source_refs']})
        disposition['case_ids'].append(case_id)
    plan['comparisons'] = [c for c in plan['comparisons']
                           if c['comparison_id'] != 'exposure_clearance_sweep']
    plan['comparisons'].append({'comparison_id': 'exposure_clearance_sweep',
                                'case_ids': list(points),
                                'fixed_conditions': 'same narrow road, 10 m pedestrian point, 5 m/s requested speed, cameras and measurement',
                                'deliberate_differences': 'frozen 0.6/1.2/1.8 m exterior placement; actual original body clearance measured separately',
                                'status': 'exact_sweep_construction_pending_cpu_proofs',
                                'source_refs': plan['cases'][0]['source_refs']})
    write(plan_path, plan)


if __name__ == '__main__':
    build()
