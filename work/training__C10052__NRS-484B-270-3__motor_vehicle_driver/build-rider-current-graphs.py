"""Bind the rider diagnostic to source-shaped live JSON graphs.

This constructs synthetic software input only. It does not simulate CARLA or
assert a legal/physical observation.
"""
import hashlib
import json
import os
from pathlib import Path
import sys


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SOURCE = HERE / 'rider-v2-bicycle-clear-primary/source'
RECIPE = HERE / 'rider-v2-bicycle-clear-primary/fixture-recipe.json'
os.environ.setdefault('SCENARIO_PIPELINE_OUTPUT_ROOT',
                      str(ROOT / '.runtime-work/c10052-rider-graph-build'))
sys.path.insert(0, str(ROOT / 'runtime/pipeline/scenario_pipeline'))
from worker_exchange.fixture_generator import _graph
from traffic_spec_adapter.adapter import write_adapter_graph


CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def write_rows(path, values):
    path.write_text(''.join(json.dumps(row, sort_keys=True) + '\n' for row in values))


def body(points):
    return [[x, y, z] for x, y in points for z in (0, 1.5)]


def actor(aid, blueprint, points, speed, heading=0):
    x = sum(p[0] for p in points) / len(points)
    y = sum(p[1] for p in points) / len(points)
    return {'actor_id': aid, 'blueprint': blueprint, 'position_m': [x, y, 0],
            'heading_deg': heading, 'velocity_mps': [speed, 0, 0],
            'speed_mps': speed, 'acceleration_mps2': [0, 0, 0],
            'body_vertices_m': body(points), 'blueprint_attributes': {},
            'light_attributes': {}}


def main():
    samples = rows(SOURCE / 'rider_native_samples.jsonl')
    evidence = rows(SOURCE / 'capture/evidence.jsonl')
    frames = rows(SOURCE / 'capture/native/frames.jsonl')
    assert len(samples) == len(evidence) == len(frames) == 480
    graph_dir = SOURCE / 'capture/native/graphs/base'
    graph_dir.mkdir(parents=True, exist_ok=True)
    for sample, event, frame in zip(samples, evidence, frames, strict=True):
        number = sample['native_frame']
        assert number == event['original_frame'] == frame['frame']
        t = sample['time_s']
        ego = actor(107, 'vehicle.lincoln.mkz_2020', sample['ego_body_xy'],
                    sample['ego_speed_mps'], event['ego']['heading_deg'])
        rider = actor(108, 'vehicle.bh.crossbike', sample['rider_body_xy'],
                      sample['rider_speed_mps'])
        pedestrian = actor(109, 'walker.pedestrian.0001',
                           [[15, -1.2], [15, -0.8],
                            [15.4, -0.8], [15.4, -1.2]], 0)
        observed = {'frame': number, 'time_s': t,
                    'participants': [ego, rider, pedestrian],
                    'world_settings': {'no_rendering_mode': False},
                    'rgb_sensors': {camera: {'frame': number} for camera in CAMERAS},
                    'map_context': {'declared_public_way_road_ids': [1],
                                    'core_assumptions': []}}
        relative = f'graphs/base/{number:08d}.adapter.json'
        graph = _graph({'path': 'capture/native/' + relative,
                        'attributes': {'frame': number,
                                       'simulation_time_s': t,
                                       'observed_evidence': observed},
                        'nodes': [], 'edges': []})
        target = graph_dir / f'{number:08d}.adapter.json'
        if target.exists():
            target.unlink()
        write_adapter_graph(graph, target)
        frame.update(base=relative, adapter_graph=relative)
        event['original_observations'] = observed
        event['ego']['speed_provenance'] = 'synthetic_native_sample'
        event['ego']['body_vertices_m'] = ego['body_vertices_m']
        event['ego']['speed_mps'] = ego['speed_mps']
    write_rows(SOURCE / 'capture/native/frames.jsonl', frames)
    write_rows(SOURCE / 'capture/evidence.jsonl', evidence)
    manifest = json.loads((SOURCE / 'capture/manifest.json').read_text())
    manifest.update(acquisition='synthetic_cpu_fixture',
                    observation_contract_version=2,
                    required_observations=[])
    (SOURCE / 'capture/manifest.json').write_text(
        json.dumps(manifest, sort_keys=True, indent=2) + '\n')
    (SOURCE / 'capture/recorder_info.txt').write_text(
        'Synthetic CPU diagnostic; CARLA recorder did not run.\n'
        'Create 107: vehicle.lincoln.mkz_2020\n'
        'Create 108: vehicle.bh.crossbike\n'
        'Create 109: walker.pedestrian.0001\n')
    recipe = json.loads(RECIPE.read_text())
    by_path = {item['path']: item for item in recipe['sources']}
    for path in (SOURCE / 'capture').rglob('*'):
        if not path.is_file():
            continue
        relative = str(path.relative_to(SOURCE))
        by_path[relative] = {'path': relative,
                             'source': str(path.relative_to(ROOT)),
                             'sha256': digest(path)}
    recipe['sources'] = [by_path[key] for key in sorted(by_path)]
    RECIPE.write_text(json.dumps(recipe, sort_keys=True, indent=2) + '\n')
    print(json.dumps({'frames': len(frames), 'graphs': len(list(graph_dir.glob('*.adapter.json'))),
                      'sources': len(recipe['sources']), 'recipe_sha256': digest(RECIPE),
                      'scope': 'synthetic CPU graph projection; no Native observation'}))


if __name__ == '__main__':
    main()
