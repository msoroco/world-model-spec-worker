"""Build a distinct 30 s synthetic conflict case and exact v2 candidate bundles."""
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
CASE = ROOT.name + '__rider_bicycle_conflict'
SELECTED = ROOT / 'selected-rider-bicycle-conflict'
CLEAR = ROOT / 'rider-30s-primary/source'
SHIFT_FRAMES = 65


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')


def body3d(body):
    return [[x, y, z] for x, y in body for z in (0, 1.5)]


def set_rider(participants, body, speed):
    rider = next(item for item in participants if item.get('actor_id') == 108)
    xs = [point[0] for point in body]
    ys = [point[1] for point in body]
    rider['position_m'] = [(min(xs) + max(xs)) / 2,
                           (min(ys) + max(ys)) / 2, 0]
    rider['body_vertices_m'] = body3d(body)
    rider['speed_mps'] = speed
    rider['velocity_mps'] = [speed, 0, 0]


def make_source():
    source = SELECTED / 'source'
    shutil.copytree(CLEAR, source, dirs_exist_ok=True)
    rider_path = source / 'rider_native_samples.jsonl'
    previous = [json.loads(line) for line in
                (CLEAR / 'rider_native_samples.jsonl').read_text().splitlines()]
    assert len(previous) == 600
    current = []
    for index, row in enumerate(previous):
        old = previous[max(0, index - SHIFT_FRAMES)]
        row = dict(row)
        row['rider_body_xy'] = old['rider_body_xy']
        row['rider_speed_mps'] = old['rider_speed_mps']
        current.append(row)
    rider_path.write_text(''.join(json.dumps(row, sort_keys=True) + '\n'
                                  for row in current))
    manifest_path = source / 'rider-source-manifest.json'
    manifest = json.loads(manifest_path.read_text())
    manifest['samples_sha256'] = sha(rider_path)
    write(manifest_path, manifest)
    evidence_path = source / 'capture/evidence.jsonl'
    evidence = [json.loads(line) for line in evidence_path.read_text().splitlines()]
    assert len(evidence) == 600
    for row, rider in zip(evidence, current):
        set_rider(row['original_observations']['participants'],
                  rider['rider_body_xy'], rider['rider_speed_mps'])
    evidence_path.write_text(''.join(json.dumps(row, sort_keys=True) + '\n'
                                     for row in evidence))
    graph_dir = source / 'capture/native/graphs/base'
    for row in current:
        path = graph_dir / f"{row['native_frame']:08d}.adapter.json"
        graph = json.loads(path.read_text())
        set_rider(graph['metadata']['observed_evidence']['participants'],
                  row['rider_body_xy'], row['rider_speed_mps'])
        path.write_text(json.dumps(graph, separators=(',', ':')) + '\n')
    specification = json.loads((ROOT / 'rider-30s-primary/diagnostic-spec.json').read_text())
    write(SELECTED / 'diagnostic-spec.json', specification)
    sources = [{'path': str(path.relative_to(source)),
                'source': str(path.relative_to(REPO)), 'sha256': sha(path)}
               for path in sorted(source.rglob('*')) if path.is_file()]
    recipe = {'format': 'worker-fixture-recipe',
              'generator': {'source': str((SELECTED / 'diagnostic-spec.json').relative_to(REPO)),
                            'sha256': sha(SELECTED / 'diagnostic-spec.json')},
              'sources': sources}
    write(SELECTED / 'fixture-recipe.json', recipe)
    return sha(SELECTED / 'fixture-recipe.json')


def make_constructions():
    spec = importlib.util.spec_from_file_location('rider_30s_builder',
        ROOT / 'build-rider-30s-primary.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    digests = {}
    for candidate in ('primary', 'fallback1', 'fallback2'):
        source = ROOT / 'draft-rider-cases/rider_bicycle_conflict' / candidate / 'construction.json'
        target = SELECTED / candidate / 'construction.json'
        module.convert(source, target)
        construction = json.loads(target.read_text())
        construction['static_checks'] = [
            'exact bicycle conflict case and original rider asset readback',
            '600 synchronized original Native frames at 20 Hz',
            'four original source camera views',
            'source-bound original rider and ego body samples']
        finalizer = next(f for f in construction['files']
                         if f['path'] == 'finalize_rider.py')
        old = "'method':'source_hashed_full_body_conflict'"
        assert finalizer['content'].count(old) == 1
        finalizer['content'] = finalizer['content'].replace(old, "'method':'finalize'")
        old_sources = "'sources':measured['source_sha256']"
        new_sources = ("'sources':{'rider_native_samples.jsonl':measured['source_sha256']['samples'], "
                       "'rider_geometry.json':measured['source_sha256']['geometry'], "
                       "'rider-source-manifest.json':measured['source_sha256']['manifest']}")
        assert finalizer['content'].count(old_sources) == 1
        finalizer['content'] = finalizer['content'].replace(old_sources, new_sources)
        write(target, construction)
        digests[candidate] = sha(target)
    return digests


def main():
    recipe_sha = make_source()
    construction_sha = make_constructions()
    manifest_path = ROOT / 'execution-manifest.json'
    manifest = json.loads(manifest_path.read_text())
    source = json.loads((ROOT / 'draft-rider-execution-manifest.json').read_text())
    entry = next(row for row in source['cases'] if row['case_id'] == CASE)
    entry['kind'] = 'delivery'
    entry['construction'] = 'selected-rider-bicycle-conflict/primary/construction.json'
    entry['construction_sha256'] = construction_sha['primary']
    entry['candidates'] = [c for c in entry['candidates']
                           if c['id'] in ('fallback1', 'fallback2')]
    for candidate in entry['candidates']:
        name = candidate['id']
        candidate['construction'] = f'selected-rider-bicycle-conflict/{name}/construction.json'
        candidate['construction_sha256'] = construction_sha[name]
    entry['fixture_recipe'] = str((SELECTED / 'fixture-recipe.json').relative_to(REPO))
    entry['measurement_contract'] = 'selected-rider-bicycle-conflict/measurement-contract.json'
    entry['native_handoff'] = {'python_env_var': 'CARLA_PYTHON',
                               'host_env_var': 'CARLA_HOST', 'port_env_var': 'CARLA_PORT'}
    write(SELECTED / 'measurement-contract.json', {
        'format': 'worker-measurement-contract', 'case_id': CASE,
        'requirements': [{'disposition_index': 0,
                          'requirement': 'NRS-484B-270-3',
                          'source': 'NRS 484B.270(3)',
                          'output_key': 'rider_conflict_observation',
                          'method': 'finalize', 'value_type': 'object',
                          'kind': 'measured',
                          'inputs': ['rider_native_samples.jsonl',
                                     'rider_geometry.json',
                                     'rider-source-manifest.json']}],
        'negative': {'remove': ['rider-source-manifest.json'],
                     'error_contains': 'Missing required source: rider-source-manifest.json'}})
    manifest['cases'] = [e for e in manifest['cases'] if e['case_id'] != CASE] + [entry]
    write(manifest_path, manifest)
    proposals_path = ROOT / 'proposals/cases.json'
    proposals = json.loads(proposals_path.read_text())
    original = next(c for c in proposals['cases']
                    if c['case_id'].endswith('__rider_bicycle_clear'))
    proposed = json.loads(json.dumps(original))
    proposed['case_id'] = CASE
    proposed['target_type'] = 'rider_yield_timing_probe'
    proposed['recording_description'] = json.loads((SELECTED / 'primary/construction.json').read_text())['recording_description']
    proposals['cases'] = [c for c in proposals['cases'] if c['case_id'] != CASE] + [proposed]
    write(proposals_path, proposals)
    plan_path = ROOT / 'case-plan.json'
    plan = json.loads(plan_path.read_text())
    disposition = plan['requirement_dispositions'][0]
    if CASE not in disposition['case_ids']:
        disposition['case_ids'].append(CASE)
    case = next(c for c in plan['cases'] if c['case_id'] == CASE)
    case['kind'] = 'delivery'
    case['planning_status'] = 'selected_v2_compatibility_pending'
    case['candidate_plans'] = [c for c in case['candidate_plans']
                               if c['id'] in ('primary', 'fallback1', 'fallback2')]
    write(plan_path, plan)
    print(json.dumps({'case_id': CASE, 'source_frames': 600,
                      'rider_shift_frames': SHIFT_FRAMES,
                      'fixture_recipe_sha256': recipe_sha,
                      'construction_sha256': construction_sha,
                      'selected': True}, indent=2))


if __name__ == '__main__':
    main()
