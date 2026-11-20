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




def build_speed6_fixture():
    import copy
    import json
    import pathlib
    import shutil
    import sys

    ROOT = pathlib.Path(__file__).resolve().parents[2]
    WORK = ROOT / 'work/testing__C158190__NRS-484B-257-1__motor_vehicle_driver'
    SOURCE = WORK / 'cases/through_mid/diagnostic-sources'
    TARGET = ROOT / '.runtime-work/c158190-speed6-fixture-v2'
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
    print(TARGET)


if __name__ == '__main__':
    if len(sys.argv) == 2 and sys.argv[1] == '--build-speed6-fixture':
        build_speed6_fixture()
    else:
        main()
