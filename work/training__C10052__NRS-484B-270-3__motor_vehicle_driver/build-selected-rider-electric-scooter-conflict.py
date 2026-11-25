"""Build a source-bound synthetic electric-scooter conflict candidate."""
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
CASE = ROOT.name + '__rider_electric_scooter_conflict'
SELECTED = ROOT / 'selected-rider-electric-scooter-conflict'
SOURCE = ROOT / 'selected-rider-bicycle-conflict/source'
BLUEPRINT = 'vehicle.c10052.electric_scooter'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def write_rows(path, values):
    path.write_text(''.join(json.dumps(row, sort_keys=True) + '\n' for row in values))


def make_source():
    source = SELECTED / 'source'
    shutil.copytree(SOURCE, source, dirs_exist_ok=True)
    rider_path = source / 'rider_native_samples.jsonl'
    rider = rows(rider_path)
    assert len(rider) == 600
    for row in rider:
        row['rider_type'] = 'electric_scooter'
    write_rows(rider_path, rider)
    manifest_path = source / 'rider-source-manifest.json'
    manifest = json.loads(manifest_path.read_text())
    manifest['rider_type'] = 'electric_scooter'
    manifest['samples_sha256'] = sha(rider_path)
    write(manifest_path, manifest)
    evidence_path = source / 'capture/evidence.jsonl'
    evidence = rows(evidence_path)
    assert len(evidence) == 600
    for row in evidence:
        actor = next(part for part in row['original_observations']['participants']
                     if part.get('actor_id') == 108)
        actor['blueprint'] = BLUEPRINT
    write_rows(evidence_path, evidence)
    graph_dir = source / 'capture/native/graphs/base'
    for row in rider:
        path = graph_dir / f"{row['native_frame']:08d}.adapter.json"
        graph = json.loads(path.read_text())
        actor = next(part for part in graph['metadata']['observed_evidence']['participants']
                     if part.get('actor_id') == 108)
        actor['blueprint'] = BLUEPRINT
        path.write_text(json.dumps(graph, separators=(',', ':')) + '\n')
    write(SELECTED / 'diagnostic-spec.json',
          json.loads((ROOT / 'rider-30s-primary/diagnostic-spec.json').read_text()))
    sources = [{'path': str(path.relative_to(source)),
                'source': str(path.relative_to(REPO)), 'sha256': sha(path)}
               for path in sorted(source.rglob('*')) if path.is_file()]
    recipe = {'format': 'worker-fixture-recipe',
              'generator': {'source': str((SELECTED / 'diagnostic-spec.json').relative_to(REPO)),
                            'sha256': sha(SELECTED / 'diagnostic-spec.json')},
              'sources': sources}
    write(SELECTED / 'fixture-recipe.json', recipe)


def make_constructions():
    spec = importlib.util.spec_from_file_location('rider_30s_builder',
                                                   ROOT / 'build-rider-30s-primary.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    digests = {}
    for candidate in ('primary', 'fallback1', 'fallback2'):
        draft = ROOT / 'draft-rider-cases/rider_electric_scooter_conflict' / candidate / 'construction.json'
        target = SELECTED / candidate / 'construction.json'
        module.convert(draft, target)
        construction = json.loads(target.read_text())
        construction['static_checks'] = [
            'exact electric bicycle conflict case and original rider asset readback',
            '600 synchronized original Native frames at 20 Hz',
            'four original source camera views',
            'source-bound original rider and ego body samples']
        finalizer = next(f for f in construction['files'] if f['path'] == 'finalize_rider.py')
        old = "'method':'source_hashed_full_body_conflict'"
        assert finalizer['content'].count(old) == 1
        finalizer['content'] = finalizer['content'].replace(old, "'method':'finalize'")
        old = "'sources':measured['source_sha256']"
        new = ("'sources':{'rider_native_samples.jsonl':measured['source_sha256']['samples'], "
               "'rider_geometry.json':measured['source_sha256']['geometry'], "
               "'rider-source-manifest.json':measured['source_sha256']['manifest']}")
        assert finalizer['content'].count(old) == 1
        finalizer['content'] = finalizer['content'].replace(old, new)
        write(target, construction)
        digests[candidate] = sha(target)
    return digests


def replace(value):
    if isinstance(value, str):
        return value.replace('ru.bicycle', 'ru.electric_scooter').replace(
            'rider_bicycle_conflict', 'rider_electric_scooter_conflict')
    if isinstance(value, list):
        return [replace(item) for item in value]
    if isinstance(value, dict):
        return {replace(key): replace(item) for key, item in value.items()}
    return value


def main():
    make_source()
    digests = make_constructions()
    manifest_path = ROOT / 'execution-manifest.json'
    manifest = json.loads(manifest_path.read_text())
    draft = json.loads((ROOT / 'draft-rider-execution-manifest.json').read_text())
    entry = next(row for row in draft['cases'] if row['case_id'] == CASE)
    entry['kind'] = 'delivery'
    entry['construction'] = 'selected-rider-electric-scooter-conflict/primary/construction.json'
    entry['construction_sha256'] = digests['primary']
    entry['candidates'] = [row for row in entry['candidates']
                           if row['id'] in ('fallback1', 'fallback2')]
    for row in entry['candidates']:
        row['construction'] = f"selected-rider-electric-scooter-conflict/{row['id']}/construction.json"
        row['construction_sha256'] = digests[row['id']]
    entry['fixture_recipe'] = str((SELECTED / 'fixture-recipe.json').relative_to(REPO))
    entry['measurement_contract'] = 'selected-rider-electric-scooter-conflict/measurement-contract.json'
    entry['native_handoff'] = {'python_env_var': 'CARLA_PYTHON',
                               'host_env_var': 'CARLA_HOST', 'port_env_var': 'CARLA_PORT'}
    bicycle = next(row for row in manifest['cases'] if row['case_id'].endswith('__rider_bicycle_conflict'))
    entry['acquisition'] = replace(bicycle['acquisition'])
    write(SELECTED / 'measurement-contract.json', {
        'format': 'worker-measurement-contract', 'case_id': CASE,
        'requirements': [{'disposition_index': 0, 'requirement': 'NRS-484B-270-3',
                          'source': 'NRS 484B.270(3)',
                          'output_key': 'rider_conflict_observation',
                          'method': 'finalize', 'value_type': 'object', 'kind': 'measured',
                          'inputs': ['rider_native_samples.jsonl', 'rider_geometry.json',
                                     'rider-source-manifest.json']}],
        'negative': {'remove': ['rider-source-manifest.json'],
                     'error_contains': 'Missing required source: rider-source-manifest.json'}})
    manifest['cases'] = [row for row in manifest['cases'] if row['case_id'] != CASE] + [entry]
    write(manifest_path, manifest)
    proposal_path = ROOT / 'proposals/cases.json'
    proposals = json.loads(proposal_path.read_text())
    base = next(row for row in proposals['cases'] if row['case_id'].endswith('__rider_bicycle_conflict'))
    proposed = replace(base)
    proposed['case_id'] = CASE
    proposed['recording_description'] = json.loads(
        (SELECTED / 'primary/construction.json').read_text())['recording_description']
    proposals['cases'] = [row for row in proposals['cases'] if row['case_id'] != CASE] + [proposed]
    write(proposal_path, proposals)
    plan_path = ROOT / 'case-plan.json'
    plan = json.loads(plan_path.read_text())
    disposition = plan['requirement_dispositions'][0]
    if CASE not in disposition['case_ids']:
        disposition['case_ids'].append(CASE)
    case = next(row for row in plan['cases'] if row['case_id'] == CASE)
    case['kind'] = 'delivery'
    case['planning_status'] = 'selected_v2_compatibility_pending'
    case['candidate_plans'] = [row for row in case['candidate_plans']
                               if row['id'] in ('primary', 'fallback1', 'fallback2')]
    write(plan_path, plan)
    print(json.dumps({'case_id': CASE, 'source_frames': 600,
                      'fixture_recipe_sha256': sha(SELECTED / 'fixture-recipe.json'),
                      'construction_sha256': digests, 'selected': True}, indent=2))


if __name__ == '__main__':
    main()
