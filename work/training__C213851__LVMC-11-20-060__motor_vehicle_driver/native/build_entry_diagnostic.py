"""Materialize textual CPU fixture recipes for both roadway-return cases."""

import hashlib
import json
import shutil
import tempfile
from pathlib import Path

from build_diagnostic import CAMERAS, bbox, write
from build_entry_return import POLICIES, ROOT
from prove_entry_measure import fixture


HERE = Path(__file__).resolve().parent
REPO = ROOT.parents[1]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def spec_for(source):
    native = [json.loads(line) for line in
              (source / 'native-rows.jsonl').read_text().splitlines()]
    graphs = []
    for index, row in enumerate(native):
        frame = row['native_frame']
        time_s = row['time_s']
        ex, ey = row['vehicle_world_xy_m']
        px, py = row['pedestrian_world_xy_m']
        tx, ty = row['approaching_world_xy_m']
        graphs.append({
            'path': f'capture/native/graphs/base/{index:08d}.adapter.json',
            'attributes': {'frame': frame, 'simulation_time_s': time_s,
                           'source': 'C213851 roadway-return CPU diagnostic',
                           'synthetic_diagnostic': True},
            'edges': [],
            'nodes': [
                {'id': 'ego', 'attributes': {
                    'entity_id': 101, 'sem_class': 'ego',
                    'vertex': [ex, ey, 1], 'forward': [1, 0, 0],
                    'threedbbox': bbox(ex, ey, 1.2, .8, 1.8)}},
                {'id': 'pedestrian', 'attributes': {
                    'entity_id': 202, 'sem_class': 'pedestrian',
                    'vertex': [px, py, 1], 'forward': [-1, 0, 0],
                    'threedbbox': bbox(px, py, .3, .3, 1.8)}},
                {'id': 'approaching', 'attributes': {
                    'entity_id': 303, 'sem_class': 'vehicle',
                    'vertex': [tx, ty, 1], 'forward': [-1, 0, 0],
                    'threedbbox': bbox(tx, ty, 1.2, .8, 1.8)}},
            ]})
    return {
        'files': {
            'capture/native/frames.jsonl':
                (source / 'capture/native/frames.jsonl').read_text(),
            'capture/recorder_info.txt':
                'Create 101: vehicle.tesla.model3 at (0,0,0)\n'
                'Create 202: walker.pedestrian.0001 at (0,0,0)\n'
                'Create 303: vehicle.audi.tt at (0,0,0)\n'
                'C213851 generated CPU diagnostic; no CARLA recording\n',
        },
        'graphs': graphs,
        'videos': [{'path': name + '.mkv', 'frames': 1200,
                    'width': width, 'height': height, 'fps': 20,
                    'color': 'black'} for name, width, height, _ in CAMERAS],
    }


def build(policy):
    from worker_exchange.fixture_generator import generate
    from worker_exchange.fixture_recipe import inspect
    destination = HERE / 'entry_return' / policy / 'diagnostic'
    destination.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=REPO / '.runtime-work',
                                     prefix='c213851-entry-diag-') as tmp:
        source = Path(tmp)
        fixture(source, policy)
        spec = spec_for(source)
        spec_path = destination / 'fixture-spec.json'
        spec_path.write_text(json.dumps(spec, separators=(',', ':')) + '\n')
        for name, _, _, _ in CAMERAS:
            (source / (name + '.mkv')).unlink()
        (source / 'capture/native/frames.jsonl').unlink()
        generate(spec, source)
        # Regenerated camera sources must be reflected in the source seal.
        from measure_entry_return import SOURCE_FILES
        seal_path = source / 'captured-source-hashes.json'
        seal = json.loads(seal_path.read_text())
        seal['sha256'] = {name: sha(source / name) for name in SOURCE_FILES}
        write(seal_path, seal)
        write(source / 'capture/manifest.json', {
            'extraction_confirmed': True, 'frames': 1200,
            'synthetic_diagnostic': True,
            'sources': {name: sha(source / name) for name in
                        ('road.xodr', 'native-rows.jsonl', 'trace.jsonl')},
        })
        sources_dir = destination / 'sources'
        sources_dir.mkdir(exist_ok=True)
        sources = []
        excluded = {'capture/native/frames.jsonl',
                    'capture/recorder_info.txt'} | {
                        name + '.mkv' for name, _, _, _ in CAMERAS}
        for path in sorted(source.rglob('*')):
            if not path.is_file():
                continue
            relative = path.relative_to(source).as_posix()
            if (relative in excluded or
                    relative.startswith('capture/native/graphs/')):
                continue
            target = sources_dir / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path, target)
            sources.append({'path': relative,
                            'source': target.relative_to(REPO).as_posix(),
                            'sha256': sha(target)})
        recipe = {'format': 'worker-fixture-recipe', 'sources': sources,
                  'generator': {'source': spec_path.relative_to(REPO).as_posix(),
                                'sha256': sha(spec_path)}}
        recipe_path = destination / 'fixture-recipe.json'
        recipe_path.write_text(json.dumps(recipe, indent=2) + '\n')
        inspect(REPO, recipe_path)
    return {'policy': policy,
            'recipe': recipe_path.relative_to(ROOT).as_posix(),
            'recipe_sha256': sha(recipe_path),
            'spec_sha256': sha(spec_path),
            'source_count': len(sources)}


if __name__ == '__main__':
    print(json.dumps([build(policy) for policy in POLICIES]))
