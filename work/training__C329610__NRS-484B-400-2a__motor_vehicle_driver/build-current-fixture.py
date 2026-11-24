"""Build source-inventoried 480-frame CPU fixtures for the active runtime."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / 'runtime/scenario_pipeline'))
sys.path.insert(1, str(ROOT / 'runtime/python'))
sys.path.insert(0, str(HERE / 'native'))
from geometry import open_drive

spec = importlib.util.spec_from_file_location('saved_fixture', HERE / 'saved-fixture-proof.py')
fixture = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixture)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_rows(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line]


def write_rows(path, rows):
    path.write_text(''.join(json.dumps(row, separators=(',', ':'), allow_nan=False) + '\n' for row in rows))


def build(suffix):
    scratch = Path(tempfile.mkdtemp(dir=ROOT / '.runtime-work', prefix='c329610-current-source-'))
    source = scratch / 'source'
    lateral = {'controlled_1': 1.75, 'controlled_2': 5.25}[suffix]
    fixture.make_base(source, suffix, lateral, 480, full_resolution=False)
    trace = read_rows(source / 'trace.jsonl')
    evidence = read_rows(source / 'capture/evidence.jsonl')
    native = read_rows(source / 'native_samples.jsonl')
    graphs = []
    frames = []
    for index, (t, e, n) in enumerate(zip(trace, evidence, native)):
        frame, time = t['frame'], t['time_s']
        x, y = n['native_center_xy_m']
        t['position_m'] = [x, y, 0.5]
        t['speed_mph'] = t['speed_mps'] / 0.44704
        t['control'] = {'throttle': 0, 'brake': 0, 'hand_brake': False}
        e.update(replay_frame=frame, replay_simulation_time_s=time, actor_id=107)
        e['ego'].update(position_m=[x, y, 0.5], heading_deg=t['heading_deg'],
                        speed_mps=t['speed_mps'], speed_provenance='synthetic_native_sample')
        road = 1 if index < 160 else 13 if index < 320 else 4
        e['world'] = {'weather': {'cloudiness': 0, 'precipitation': 0, 'wetness': 0,
                                  'fog_density': 0},
                      'road_projection': {'road_id': road, 'section_id': 0,
                                          'lane_id': -1, 's_m': x + 100}}
        box = [[x - 2.6, y - 1.1, 0], [x - 2.6, y - 1.1, 1.5],
               [x + 2.6, y + 1.1, 0], [x + 2.6, y + 1.1, 1.5]]
        name = f'{frame:08d}'
        graphs.append({'path': f'capture/native/graphs/base/{name}.adapter.json',
                       'attributes': {'frame': frame, 'simulation_time_s': time,
                                      'synthetic_diagnostic': True},
                       'nodes': [{'id': 'ego', 'attributes': {'sem_class': 'ego',
                                                            'entity_id': 107,
                                                            'vertex': [x, y, 0.5],
                                                            'forward': [1.0, 0.0, 0.0],
                                                            'threedbbox': box}}],
                       'edges': []})
        frames.append({'frame': frame, 'simulation_time': time, 'time_s': time,
                       'base': f'graphs/base/{name}.pkl',
                       'abstract': f'graphs/abstract/{name}.pkl',
                       'synthetic_diagnostic': True})
    assert len(trace) == len(evidence) == len(native) == len(frames) == 480
    write_rows(source / 'trace.jsonl', trace)
    write_rows(source / 'capture/evidence.jsonl', evidence)
    (source / 'capture/native').mkdir(parents=True, exist_ok=True)
    write_rows(source / 'capture/native/frames.jsonl', frames)
    (source / 'road.xodr').write_text(open_drive())
    (source / 'capture/recorder_info.txt').write_text('Create 107: vehicle.lincoln.mkz_2020\n')
    manifest = json.loads((source / 'capture/manifest.json').read_text())
    manifest.update(sources={'road.xodr': sha(source / 'road.xodr'),
                             'trace.jsonl': sha(source / 'trace.jsonl')},
                    synthetic_diagnostic=True)
    (source / 'capture/manifest.json').write_text(json.dumps(manifest, separators=(',', ':')) + '\n')
    destination = HERE / 'current-fixture' / suffix
    destination.mkdir(parents=True, exist_ok=True)
    files = []
    for path in sorted(source.rglob('*')):
        if not path.is_file() or path.suffix == '.mkv' or path.name == 'config.json':
            continue
        relative = path.relative_to(source)
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, target)
        files.append({'path': relative.as_posix(), 'source': target.relative_to(ROOT).as_posix(),
                      'sha256': sha(target)})
    diagnostic = {'files': {}, 'graphs': graphs,
                  'videos': [{'path': name, 'frames': 480, 'width': width, 'height': height,
                              'fps': 20, 'color': 'black'}
                             for name, width, height in [('overview.mkv', 1920, 1080),
                                                         ('approach.mkv', 1280, 720),
                                                         ('reference_corner.mkv', 1280, 720),
                                                         ('driver_reference.mkv', 1280, 720)]]}
    diagnostic_path = HERE / f'current-{suffix}-diagnostic.json'
    diagnostic_path.write_text(json.dumps(diagnostic, separators=(',', ':')) + '\n')
    recipe = {'format': 'worker-fixture-recipe', 'sources': files,
              'generator': {'source': diagnostic_path.relative_to(ROOT).as_posix(),
                            'sha256': sha(diagnostic_path)}}
    recipe_path = HERE / f'current-{suffix}-recipe.json'
    recipe_path.write_text(json.dumps(recipe, indent=2) + '\n')
    print(json.dumps({'case': suffix, 'recipe': str(recipe_path),
                      'recipe_sha256': sha(recipe_path), 'diagnostic_sha256': sha(diagnostic_path),
                      'source_count': len(files), 'graph_count': len(graphs)}))


if __name__ == '__main__':
    if 'SCENARIO_PIPELINE_OUTPUT_ROOT' not in os.environ:
        raise SystemExit('Export SCENARIO_PIPELINE_OUTPUT_ROOT under .runtime-work first')
    for suffix in ('controlled_1', 'controlled_2'):
        build(suffix)
