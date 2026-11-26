"""Build source-shaped CPU fixtures; no original Native capture is claimed."""

import hashlib
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

from prove_sidewalk import fixture, reseal

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
REPO = HERE.parents[2]
CAMERAS = (
    ('overview', 1920, 1080, 80),
    ('approach', 1280, 720, 80),
    ('reference_corner', 1280, 720, 75),
    ('driver_reference', 1280, 720, 80),
)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, separators=(',', ':')) + '\n')


def bbox(x, y, half_x, half_y, height):
    return [[x + dx, y + dy, z] for dx in (-half_x, half_x)
            for dy in (-half_y, half_y) for z in (0.2, height)]


def spec_for(source):
    native = [json.loads(line) for line in
              (source / 'native-rows.jsonl').read_text().splitlines()]
    graphs = []
    for index, row in enumerate(native):
        frame = row['native_frame']
        time_s = row['time_s']
        ex, ey = row['vehicle_world_xy_m']
        px, py = row['pedestrian_world_xy_m']
        graphs.append({
            'path': f'capture/native/graphs/base/{index:08d}.adapter.json',
            'attributes': {'frame': frame, 'simulation_time_s': time_s,
                           'source': 'C213851 CPU diagnostic',
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
            ]})
    return {
        'files': {
            'capture/native/frames.jsonl':
                (source / 'capture/native/frames.jsonl').read_text(),
            'capture/recorder_info.txt':
                'Create 101: vehicle.tesla.model3 at (0,0,0)\n'
                'Create 202: walker.pedestrian.0001 at (0,0,0)\n'
                'C213851 generated CPU diagnostic; no CARLA recording\n',
        },
        'graphs': graphs,
        'videos': [{'path': name + '.mkv', 'frames': 600,
                    'width': width, 'height': height, 'fps': 20,
                    'color': 'black'} for name, width, height, _ in CAMERAS],
    }


def build(suffix):
    from worker_exchange.fixture_generator import generate
    from worker_exchange.fixture_recipe import inspect
    destination = HERE / suffix / 'diagnostic'
    destination.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=REPO / '.runtime-work',
                                     prefix='c213851-diag-') as tmp:
        source = Path(tmp)
        fixture(source, suffix)
        spec = spec_for(source)
        spec_path = destination / 'fixture-spec.json'
        spec_path.write_text(json.dumps(spec, separators=(',', ':')) + '\n')
        for name, _, _, _ in CAMERAS:
            (source / (name + '.mkv')).unlink()
        (source / 'capture/native/frames.jsonl').unlink()
        generate(spec, source)
        reseal(source)
        write(source / 'capture/manifest.json', {
            'extraction_confirmed': True, 'frames': 600,
            'synthetic_diagnostic': True,
            'sources': {name: sha(source / name) for name in
                        ('road.xodr', 'native-rows.jsonl', 'trace.jsonl')},
        })
        source_dir = destination / 'sources'
        source_dir.mkdir(exist_ok=True)
        sources = []
        excluded = {'capture/native/frames.jsonl',
                    'capture/recorder_info.txt'} | {
                        name + '.mkv' for name, _, _, _ in CAMERAS}
        for path in sorted(source.rglob('*')):
            if not path.is_file():
                continue
            relative = path.relative_to(source).as_posix()
            if relative in excluded or relative.startswith(
                    'capture/native/graphs/'):
                continue
            target = source_dir / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path, target)
            sources.append({'path': relative,
                            'source': target.relative_to(REPO).as_posix(),
                            'sha256': sha(target)})
        recipe = {'format': 'worker-fixture-recipe', 'sources': sources,
                  'generator': {
                      'source': spec_path.relative_to(REPO).as_posix(),
                      'sha256': sha(spec_path)}}
        recipe_path = destination / 'fixture-recipe.json'
        recipe_path.write_text(json.dumps(recipe, indent=2) + '\n')
        inspect(REPO, recipe_path)
    return {'suffix': suffix,
            'recipe': recipe_path.relative_to(ROOT).as_posix(),
            'recipe_sha256': sha(recipe_path),
            'spec_sha256': sha(spec_path),
            'source_count': len(sources)}


if __name__ == '__main__':
    print(json.dumps([build(suffix) for suffix in
                      ('stop_before_sidewalk', 'cross_without_stop')]))
