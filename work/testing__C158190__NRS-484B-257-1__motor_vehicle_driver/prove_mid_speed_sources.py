"""Prove the unselected 4 m/s draft's saved-source finalizer on CPU fixtures.

The input is a synthetic Native-shaped recipe. This is a source/procedure check,
not a physical or legal acceptance receipt or a canonical compatibility proof.
"""

import hashlib
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / 'runtime/scenario_pipeline'))
from worker_exchange.fixture_recipe import materialize as materialize_recipe
from worker_exchange.runtime_cli import materialize as materialize_construction, execution_env
from worker_exchange.saved_processing import copy_sources
from worker_exchange.common import digest, tree

CASE = HERE.name + '__yield_nearest_view_mid_speed'
MANIFEST = HERE / 'mid-speed-draft-manifest.json'
RECIPE = HERE / 'cases/through_mid/diagnostic-recipe.json'
BASE = REPO / '.runtime-work/c158190-mid-sources-v1'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def run_finalizer(folder):
    return subprocess.run(
        [sys.executable, str(folder / 'finalizer.py'), '--attempt', str(folder),
         '--output', str(folder / 'analysis-report.json')],
        cwd=folder, env=execution_env(), text=True,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=300)


def prepare(folder, fixture):
    materialize_construction(MANIFEST, CASE, folder)
    copy_sources(fixture, folder)


def main():
    if BASE.exists():
        raise ValueError('Retain prior source proof; choose a fresh output name')
    BASE.mkdir(parents=True)
    fixture = BASE / 'fixture'
    materialize_recipe(REPO, RECIPE, fixture)
    positive = BASE / 'positive'
    prepare(positive, fixture)
    source_hash = digest(tree(positive / 'capture'))
    original_hashes = {name: sha(positive / name) for name in
                       ('approach_history.jsonl', 'visibility_rays.jsonl',
                        'interaction_history.jsonl', 'trace.jsonl',
                        'overview.mkv', 'approach.mkv', 'reference_corner.mkv',
                        'driver_reference.mkv')}
    result = run_finalizer(positive)
    (HERE / 'cases/through_mid/source-positive-current.log').write_text(result.stdout)
    if result.returncode:
        raise ValueError(f'Positive finalizer exited {result.returncode}')
    if digest(tree(positive / 'capture')) != source_hash:
        raise ValueError('Finalizer rewrote original Native capture')
    if any(sha(positive / name) != expected for name, expected in original_hashes.items()):
        raise ValueError('Finalizer rewrote original source')
    report = json.loads((positive / 'analysis-report.json').read_text())
    measurement = report['measurements']['speed_at_closest_view_mps']['value']
    if measurement != 4.0 or report['case_id'] != CASE:
        raise ValueError('Draft saved measurement is not the selected 4 m/s case')
    negative = BASE / 'negative'
    prepare(negative, fixture)
    (negative / 'visibility_rays.jsonl').unlink()
    failure = run_finalizer(negative)
    (HERE / 'cases/through_mid/source-negative-current.log').write_text(failure.stdout)
    if failure.returncode == 0 or 'Missing required source: visibility_rays.jsonl' not in failure.stdout:
        raise ValueError('Missing original sight rays were not rejected')
    receipt = {
        'format': 'c158190-unselected-source-finalizer-diagnostic',
        'case_id': CASE,
        'physical_acceptance_claimed': False,
        'canonical_compatibility_claimed': False,
        'recipe_sha256': sha(RECIPE),
        'construction_sha256': sha(HERE / 'cases/through_mid/construction.json'),
        'fixture_source_count': len(json.loads(RECIPE.read_text())['sources']),
        'positive_measurement_mps': measurement,
        'negative_removed_source': 'visibility_rays.jsonl',
        'negative_exit_code': failure.returncode,
        'positive_analysis_sha256': sha(positive / 'analysis-report.json'),
        'positive_log_sha256': sha(HERE / 'cases/through_mid/source-positive-current.log'),
        'negative_log_sha256': sha(HERE / 'cases/through_mid/source-negative-current.log'),
    }
    path = HERE / 'cases/through_mid/source-finalizer-diagnostic.json'
    path.write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps(receipt, indent=2))




def build_speed6_fixture(output):
    import copy
    import json
    import pathlib
    import shutil
    import sys

    ROOT = pathlib.Path(__file__).resolve().parents[2]
    WORK = ROOT / 'work/testing__C158190__NRS-484B-257-1__motor_vehicle_driver'
    SOURCE = WORK / 'cases/through_mid/diagnostic-sources'
    TARGET = (ROOT / output).resolve()
    if ROOT / '.runtime-work' not in TARGET.parents:
        raise ValueError('Diagnostic output belongs under .runtime-work')
    CASE = 'testing__C158190__NRS-484B-257-1__motor_vehicle_driver__yield_nearest_view_speed_6'
    sys.path.insert(0, str(ROOT / 'runtime/scenario_pipeline'))
    from worker_exchange.runtime_cli import materialize


    def rows(path):
        return [json.loads(line) for line in path.read_text().splitlines()]


    def write_rows(path, content):
        path.write_text(''.join(json.dumps(row, separators=(',', ':'), allow_nan=False) + '\n' for row in content))


    def body(x):
        return [[x + dx, y, z] for dx in (-1.5, 1.5) for y in (1.1, 2.5) for z in (0, 1.5)]


    def projection(x):
        if x < -8:
            return 158190, x + 80
        if x < 8:
            return 158192, x + 8
        return 158193, x - 8


    if TARGET.exists():
        raise SystemExit('Choose fresh fixture directory')
    materialize(WORK / 'view-speed-6-draft-manifest.json', CASE, TARGET)
    for source in SOURCE.rglob('*'):
        if source.is_file():
            target = TARGET / source.relative_to(SOURCE)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)

    approach = rows(TARGET / 'approach_history.jsonl')
    approach[0]['ego_speed_mps'] = 8.0
    approach[1]['ego_speed_mps'] = 6.0
    approach[1]['distance_to_intersection_m'] = 11.65
    write_rows(TARGET / 'approach_history.jsonl', approach)
    rays = rows(TARGET / 'visibility_rays.jsonl')
    rays[1]['distance_to_intersection_m'] = 11.65
    write_rows(TARGET / 'visibility_rays.jsonl', rays)
    samples = json.loads((TARGET / 'visibility_samples.json').read_text())
    samples[1]['distance_to_intersection_m'] = 11.65
    (TARGET / 'visibility_samples.json').write_text(json.dumps(samples, indent=2) + '\n')

    trace = rows(TARGET / 'trace.jsonl')
    interaction = rows(TARGET / 'interaction_history.jsonl')
    evidence = rows(TARGET / 'capture/evidence.jsonl')
    for i, (t, interaction_row, e) in enumerate(zip(trace, interaction, evidence)):
        x = round(min(62.6, -20.0 + (0 if i == 0 else 0.35 + 0.3 * (i - 1))), 4)
        speed = 8.0 if i == 0 else (6.0 if x < 62.6 else 0.0)
        vertices = body(x)
        road, s = projection(x)
        t['position_m'][0] = x
        t['position']['x'] = x
        t['speed_mps'] = speed
        t['speed_mph'] = speed * 2.2369362920544025
        t['velocity_mps'][0] = speed
        interaction_row['ego']['body_vertices_m'] = copy.deepcopy(vertices)
        interaction_row['ego']['road_id'] = road
        e['ego']['position_m'][0] = x
        e['ego']['speed_mps'] = speed
        e['ego']['body_vertices_m'] = copy.deepcopy(vertices)
        e['world']['road_projection'].update(road_id=road, s_m=round(s, 4))
        e['visibility']['ego_body_samples_m'] = copy.deepcopy(vertices) + [[x, 1.8, 0]]
        e['visibility']['ego_projection']['road_id'] = road
        for observed in e['original_observations']['participants']:
            observed['blueprint_attributes'] = {'base_type': 'car'}
        participant = next(p for p in e['original_observations']['participants'] if p['actor_id'] == 101)
        participant['position_m'][0] = x
        participant['speed_mps'] = speed
        participant['velocity_mps'][0] = speed
        participant['body_vertices_m'] = copy.deepcopy(vertices)
        participant['accel_longitudinal_mps2'] = -40.0 if i == 1 else 0.0
    write_rows(TARGET / 'trace.jsonl', trace)
    write_rows(TARGET / 'interaction_history.jsonl', interaction)
    write_rows(TARGET / 'capture/evidence.jsonl', evidence)
    capture = json.loads((TARGET / 'capture/manifest.json').read_text())
    capture['case_id'] = CASE
    import hashlib
    capture['sources']['trace.jsonl'] = hashlib.sha256((TARGET / 'trace.jsonl').read_bytes()).hexdigest()
    (TARGET / 'capture/manifest.json').write_text(json.dumps(capture, indent=2) + '\n')
    native_frames = rows(TARGET / 'capture/native/frames.jsonl')
    for row in native_frames:
        for key in ('base', 'abstract'):
            row[key] = row[key].replace('.pkl', '.adapter.json')
        row['adapter_graph'] = row['base']
    write_rows(TARGET / 'capture/native/frames.jsonl', native_frames)
    print(TARGET)


def build_matched_approach_drafts(output):
    """Offline prove 8 m/s approach variants of the selected 2/4 m/s cases.

    These are draft constructions under ignored runtime work. They do not
    replace either selected manifest entry or its existing receipt bindings.
    """
    import copy

    target = (REPO / output).resolve()
    if REPO / '.runtime-work' not in target.parents or target.exists():
        raise ValueError('Choose a fresh directory under .runtime-work')
    target.mkdir(parents=True)
    evidence = []
    for name, source in (('view_speed_2', HERE / 'construction.json'),
                         ('view_speed_4', HERE / 'cases/through_mid/construction.json')):
        proposal = copy.deepcopy(json.loads(source.read_text()))
        controller = next(item for item in proposal['files']
                          if item['path'] == 'yield_controller.py')
        old = 'approach_speed_mps: float = 6.0'
        if controller['content'].count(old) != 1:
            raise ValueError('Selected controller approach default changed')
        controller['content'] = controller['content'].replace(
            old, 'approach_speed_mps: float = 8.0')
        for item in proposal['files']:
            if item['path'] == 'tests/test_yield_controller.py':
                item['content'] = item['content'].replace(
                    'through_vehicle_clear=False), 6)',
                    'through_vehicle_clear=False), 8)')
            elif item['path'] == 'tests/test_yield_motion.py':
                item['content'] = item['content'].replace(
                    "self.assertEqual(fast['ego_target_mps'], 6.)",
                    "self.assertEqual(fast['ego_target_mps'], 8.)")
            elif item['path'] == 'tests/test_mid_speed.py':
                item['content'] = item['content'].replace(
                    'through_vehicle_clear=False), 6.0)',
                    'through_vehicle_clear=False), 8.0)')
        proposal['mechanisms'].append(
            'draft matched 8 m/s ego approach for 2/4/6 m/s view-speed comparison')
        folder = target / name
        folder.mkdir()
        for item in proposal['files']:
            path = folder / item['path']
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(item['content'])
        (folder / 'construction.json').write_text(json.dumps(proposal, indent=2) + '\n')
        log = folder / 'offline.log'
        with log.open('w') as stream:
            for args in ([sys.executable, str(folder / proposal['entrypoint']), '--check'],
                         [sys.executable, '-m', 'unittest', 'discover', '-s', 'tests']):
                result = subprocess.run(args, cwd=folder, env=execution_env(),
                                        stdout=stream, stderr=subprocess.STDOUT,
                                        timeout=300)
                if result.returncode:
                    raise ValueError(f'{name} draft offline check failed: {result.returncode}; {log}')
        evidence.append({'case_id': proposal['case_id'], 'draft_construction': str(folder / 'construction.json'),
                         'draft_construction_sha256': sha(folder / 'construction.json'),
                         'offline_log': str(log), 'offline_log_sha256': sha(log),
                         'offline_exit_code': 0})
    (target / 'receipt.json').write_text(json.dumps({
        'format': 'c158190-matched-approach-offline-draft',
        'approach_speed_mps': 8.0, 'view_speeds_mps': [2.0, 4.0, 6.0],
        'selected_manifest_changed': False, 'cases': evidence,
    }, indent=2) + '\n')
    print(target / 'receipt.json')


def prove_matched_approach_sources(output):
    """Run saved finalizers against synthetic, internally joined 8 m/s sources."""
    import copy
    import shutil

    target = (REPO / output).resolve()
    if REPO / '.runtime-work' not in target.parents or target.exists():
        raise ValueError('Choose a fresh directory under .runtime-work')
    source = REPO / '.runtime-work/c158190-speed6-fixture-v4'
    drafts = REPO / '.runtime-work/c158190-matched-approach-drafts-20261120-v3'
    if not source.is_dir() or not (drafts / 'receipt.json').is_file():
        raise ValueError('Current speed-6 source and matched construction drafts required')
    target.mkdir(parents=True)
    media = target / 'shared-media'
    materialize_recipe(REPO, HERE / 'cases/view_speed_6/diagnostic-recipe.json', media)

    def rows(path):
        return [json.loads(line) for line in path.read_text().splitlines()]

    def put_rows(path, values):
        path.write_text(''.join(json.dumps(value, separators=(',', ':'), allow_nan=False) + '\n'
                                for value in values))

    def body(x):
        return [[x + dx, y, z] for dx in (-1.5, 1.5)
                for y in (1.1, 2.5) for z in (0, 1.5)]

    receipt = {'format': 'c158190-matched-approach-source-finalizer-draft',
               'synthetic_fixture': True, 'approach_speed_mps': 8.0, 'cases': []}
    for name, view in (('view_speed_2', 2.0), ('view_speed_4', 4.0)):
        folder = target / name
        shutil.copytree(source, folder)
        for camera in ('overview', 'approach', 'reference_corner', 'driver_reference'):
            shutil.copyfile(media / (camera + '.mkv'), folder / (camera + '.mkv'))
        proposal = json.loads((drafts / name / 'construction.json').read_text())
        for item in proposal['files']:
            path = folder / item['path']
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(item['content'])
        (folder / 'construction.json').write_text(json.dumps(proposal, indent=2) + '\n')
        (folder / 'candidate-selection.json').unlink()
        case = proposal['case_id']
        approach = rows(folder / 'approach_history.jsonl')
        approach[0]['ego_speed_mps'] = 8.0
        approach[1]['ego_speed_mps'] = view
        put_rows(folder / 'approach_history.jsonl', approach)
        trace = rows(folder / 'trace.jsonl')
        interaction = rows(folder / 'interaction_history.jsonl')
        evidence = rows(folder / 'capture/evidence.jsonl')
        if not (len(trace) == len(interaction) == len(evidence) == 600):
            raise ValueError('Expected 600 joined source frames')
        for i, (t, inter, e) in enumerate(zip(trace, interaction, evidence)):
            x = round(min(62.6, -20.0 + (0 if i == 0 else .35 + view / 20 * (i - 1))), 4)
            speed = 8.0 if i == 0 else (view if x < 62.6 else 0.0)
            vertices = body(x)
            road, s = ((158190, x + 80) if x < -8 else
                       (158192, x + 8) if x < 8 else (158193, x - 8))
            t['position_m'][0] = x
            t['position']['x'] = x
            t['speed_mps'] = speed
            t['speed_mph'] = speed * 2.2369362920544025
            t['velocity_mps'][0] = speed
            inter['ego']['body_vertices_m'] = copy.deepcopy(vertices)
            inter['ego']['road_id'] = road
            e['ego']['position_m'][0] = x
            e['ego']['speed_mps'] = speed
            e['ego']['body_vertices_m'] = copy.deepcopy(vertices)
            e['world']['road_projection'].update(road_id=road, s_m=round(s, 4))
            e['visibility']['ego_body_samples_m'] = copy.deepcopy(vertices) + [[x, 1.8, 0]]
            e['visibility']['ego_projection']['road_id'] = road
            actor = next(p for p in e['original_observations']['participants']
                         if p['actor_id'] == 101)
            actor['position_m'][0] = x
            actor['speed_mps'] = speed
            actor['velocity_mps'][0] = speed
            actor['body_vertices_m'] = copy.deepcopy(vertices)
            actor['accel_longitudinal_mps2'] = (view - 8.0) / .05 if i == 1 else 0.0
        put_rows(folder / 'trace.jsonl', trace)
        put_rows(folder / 'interaction_history.jsonl', interaction)
        put_rows(folder / 'capture/evidence.jsonl', evidence)
        capture = json.loads((folder / 'capture/manifest.json').read_text())
        capture['case_id'] = case
        capture['sources']['trace.jsonl'] = sha(folder / 'trace.jsonl')
        (folder / 'capture/manifest.json').write_text(json.dumps(capture, indent=2) + '\n')
        original = {p: sha(folder / p) for p in
                    ('trace.jsonl', 'approach_history.jsonl', 'interaction_history.jsonl',
                     'capture/evidence.jsonl', 'capture/manifest.json')}
        result = run_finalizer(folder)
        log = folder / 'source-finalizer.log'
        log.write_text(result.stdout)
        if result.returncode:
            raise ValueError(f'{name} saved finalizer failed: {result.returncode}; {log}')
        if any(sha(folder / p) != expected for p, expected in original.items()):
            raise ValueError(f'{name} saved finalizer rewrote original source')
        report = json.loads((folder / 'analysis-report.json').read_text())
        measured = report['measurements']['speed_at_closest_view_mps']['value']
        if report['case_id'] != case or measured != view:
            raise ValueError(f'{name} saved speed measurement differs from plan')
        negative = target / (name + '-missing-rays')
        shutil.copytree(folder, negative)
        (negative / 'analysis-report.json').unlink()
        (negative / 'result.json').unlink()
        shutil.rmtree(negative / 'channels')
        (negative / 'visibility_rays.jsonl').unlink()
        failure = run_finalizer(negative)
        negative_log = negative / 'source-finalizer-negative.log'
        negative_log.write_text(failure.stdout)
        if failure.returncode == 0 or 'Missing required source: visibility_rays.jsonl' not in failure.stdout:
            raise ValueError(f'{name} missing-ray source was not rejected')
        receipt['cases'].append({'case_id': case, 'view_speed_mps': view,
                                 'analysis_sha256': sha(folder / 'analysis-report.json'),
                                 'log_sha256': sha(log), 'source_sha256': original,
                                 'finalizer_exit_code': 0,
                                 'negative_removed_source': 'visibility_rays.jsonl',
                                 'negative_exit_code': failure.returncode,
                                 'negative_log_sha256': sha(negative_log)})
    (target / 'receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print(target / 'receipt.json')


def build_linked_approach_draft(variant, output):
    """Rejoin a selected comparison case to the sampled 8 m/s approach.

    Keep the case's through-actor history and view speed. The first sampled
    ego displacement uses the mean of approach and view speeds; later ego
    positions shift by the resulting offset. This is synthetic CPU evidence.
    """
    import copy
    import shutil

    if variant not in ('clear', 'no_slow', 'through_entered'):
        raise ValueError('Unknown linked comparison case')
    target = (REPO / output).resolve()
    if REPO / '.runtime-work' not in target.parents or target.exists():
        raise ValueError('Choose a fresh directory under .runtime-work')
    draft = REPO / '.runtime-work/c158190-linked-approach8-drafts-v1' / variant
    if not (draft / 'construction.json').is_file():
        raise ValueError('Offline-passing linked construction draft required')
    # Use the current adapter-JSON media generator, then restore every original
    # linked-case source packet; old linked generator specs still name pickle graphs.
    materialize_recipe(REPO, HERE / 'diagnostic-recipe.json', target)
    source = HERE / 'cases' / variant / 'diagnostic-sources'
    for path in source.rglob('*'):
        if path.is_file():
            dest = target / path.relative_to(source)
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path, dest)
    for item in json.loads((draft / 'construction.json').read_text())['files']:
        dest = target / item['path']
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(item['content'])
    shutil.copyfile(draft / 'construction.json', target / 'construction.json')

    def rows(name):
        return [json.loads(line) for line in (target / name).read_text().splitlines()]

    def put(name, values):
        (target / name).write_text(''.join(
            json.dumps(value, separators=(',', ':'), allow_nan=False) + '\n'
            for value in values))

    view = {'clear': 4.0, 'no_slow': 6.0, 'through_entered': 2.0}[variant]
    approach = rows('approach_history.jsonl')
    old_step = 12.0 - approach[1]['distance_to_intersection_m']
    new_step = (8.0 + view) * .05 / 2
    offset = round(new_step - old_step, 4)
    approach[0]['ego_speed_mps'] = 8.0
    boundary_epsilon = 0.0001 if variant in ('clear', 'through_entered') else 0.0
    approach[1]['distance_to_intersection_m'] = round(12.0 - new_step - boundary_epsilon, 4)
    put('approach_history.jsonl', approach)
    rays = rows('visibility_rays.jsonl')
    rays[1]['distance_to_intersection_m'] = approach[1]['distance_to_intersection_m']
    put('visibility_rays.jsonl', rays)
    samples = json.loads((target / 'visibility_samples.json').read_text())
    samples[1]['distance_to_intersection_m'] = approach[1]['distance_to_intersection_m']
    (target / 'visibility_samples.json').write_text(json.dumps(samples, indent=2) + '\n')

    trace = rows('trace.jsonl')
    bodies = rows('interaction_history.jsonl')
    evidence = rows('capture/evidence.jsonl')
    if not (len(trace) == len(bodies) == len(evidence) == 600):
        raise ValueError('Expected 600 joined source frames')
    for i, (t, body_row, event) in enumerate(zip(trace, bodies, evidence)):
        shift = offset + boundary_epsilon if i else 0.0
        x = round(t['position_m'][0] + shift, 4)
        speed = 8.0 if i == 0 else t['speed_mps']
        t['position_m'][0] = x
        t['position']['x'] = x
        t['speed_mps'] = speed
        t['speed_mph'] = speed * 2.2369362920544025
        t['velocity_mps'][0] = speed
        for vertex in body_row['ego']['body_vertices_m']:
            vertex[0] = round(vertex[0] + shift, 4)
        road, station = ((158190, x + 80) if x < -8 else
                         (158192, x + 8) if x < 8 else (158193, x - 8))
        body_row['ego']['road_id'] = road
        event['ego']['position_m'][0] = x
        event['ego']['speed_mps'] = speed
        for vertex in event['ego']['body_vertices_m']:
            vertex[0] = round(vertex[0] + shift, 4)
        event['world']['road_projection'].update(road_id=road, s_m=round(station, 4))
        event['visibility']['ego_projection']['road_id'] = road
        for vertex in event['visibility']['ego_body_samples_m']:
            vertex[0] = round(vertex[0] + shift, 4)
        ego = next(p for p in event['original_observations']['participants']
                   if p['actor_id'] == 101)
        ego['position_m'][0] = x
        ego['speed_mps'] = speed
        ego['velocity_mps'][0] = speed
        for vertex in ego['body_vertices_m']:
            vertex[0] = round(vertex[0] + shift, 4)
        ego['accel_longitudinal_mps2'] = (view - 8.0) / .05 if i == 1 else 0.0
    for event in evidence:
        for participant in event['original_observations']['participants']:
            if participant.get('blueprint', '').startswith('vehicle.'):
                participant.setdefault('blueprint_attributes', {'base_type': 'car'})
    put('trace.jsonl', trace)
    put('interaction_history.jsonl', bodies)
    put('capture/evidence.jsonl', evidence)
    capture = json.loads((target / 'capture/manifest.json').read_text())
    capture['sources']['trace.jsonl'] = sha(target / 'trace.jsonl')
    (target / 'capture/manifest.json').write_text(json.dumps(capture, indent=2) + '\n')
    native_frames = rows('capture/native/frames.jsonl')
    for frame in native_frames:
        for key in ('base', 'abstract'):
            frame[key] = frame[key].replace('.pkl', '.adapter.json')
        frame['adapter_graph'] = frame['base']
    put('capture/native/frames.jsonl', native_frames)
    specification = json.loads((HERE / 'cases' / variant / 'diagnostic.json').read_text())
    by_frame = {event['original_frame']: event for event in evidence}
    for graph in specification['graphs']:
        graph['path'] = graph['path'].replace('.pkl', '.adapter.json')
        frame = graph['attributes']['frame']
        graph['attributes']['observed_evidence'] = by_frame[frame]['original_observations']
    from worker_exchange.fixture_generator import inspect as inspect_generated
    inspect_generated(specification)
    (target / 'diagnostic-candidate.json').write_text(
        json.dumps(specification, separators=(',', ':'), allow_nan=False) + '\n')
    originals = {name: sha(target / name) for name in
                 ('approach_history.jsonl', 'visibility_rays.jsonl',
                  'interaction_history.jsonl', 'trace.jsonl',
                  'capture/evidence.jsonl', 'capture/manifest.json',
                  'capture/native/frames.jsonl')}
    result = run_finalizer(target)
    (target / 'source-finalizer.log').write_text(result.stdout)
    if result.returncode:
        raise ValueError(f'{variant} finalizer exited {result.returncode}')
    if any(sha(target / name) != value for name, value in originals.items()):
        raise ValueError('Draft finalizer rewrote original source')
    report = json.loads((target / 'analysis-report.json').read_text())
    measured = report['measurements']['speed_at_closest_view_mps']['value']
    if measured != view:
        raise ValueError('Source-bound view speed differs from case plan')
    negative = target.parent / (target.name + '-missing-rays')
    shutil.copytree(target, negative)
    for name in ('analysis-report.json', 'result.json'):
        path = negative / name
        if path.exists():
            path.unlink()
    channels = negative / 'channels'
    if channels.exists():
        shutil.rmtree(channels)
    (negative / 'visibility_rays.jsonl').unlink()
    failure = run_finalizer(negative)
    (negative / 'source-finalizer-negative.log').write_text(failure.stdout)
    if failure.returncode == 0 or 'Missing required source: visibility_rays.jsonl' not in failure.stdout:
        raise ValueError('Missing original sight rays were not rejected')
    receipt = {'format': 'c158190-linked-approach8-source-draft',
               'variant': variant, 'view_speed_mps': view,
               'sampled_approach_speed_mps': 8.0,
               'original_source_sha256': originals,
               'construction_sha256': sha(target / 'construction.json'),
               'diagnostic_candidate_sha256': sha(target / 'diagnostic-candidate.json'),
               'analysis_sha256': sha(target / 'analysis-report.json'),
               'finalizer_exit_code': 0, 'selected_manifest_changed': False}
    receipt['negative_removed_source'] = 'visibility_rays.jsonl'
    receipt['negative_exit_code'] = failure.returncode
    receipt['negative_log_sha256'] = sha(negative / 'source-finalizer-negative.log')
    (target / 'receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print(target / 'receipt.json')


if __name__ == '__main__':
    if len(sys.argv) == 3 and sys.argv[1] == '--build-speed6-fixture':
        build_speed6_fixture(sys.argv[2])
    elif len(sys.argv) == 3 and sys.argv[1] == '--build-matched-approach-drafts':
        build_matched_approach_drafts(sys.argv[2])
    elif len(sys.argv) == 3 and sys.argv[1] == '--prove-matched-approach-sources':
        prove_matched_approach_sources(sys.argv[2])
    elif len(sys.argv) == 4 and sys.argv[1] == '--build-linked-approach-draft':
        build_linked_approach_draft(sys.argv[2], sys.argv[3])
    else:
        main()
