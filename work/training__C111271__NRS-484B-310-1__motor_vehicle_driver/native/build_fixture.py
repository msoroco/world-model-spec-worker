"""Source-hashed six-case software fixture, never physical signal evidence."""

import hashlib
import json
import os
from pathlib import Path

from prove_source_measurement import make_sources

ROOT = Path(__file__).resolve().parent.parent
REPO = ROOT.parents[1]
SCRATCH = Path(os.environ['SCENARIO_PIPELINE_OUTPUT_ROOT'])
BASE = REPO / 'work/training__C230266__NRS-484B-280-1c__motor_vehicle_driver/selected-generator-probe_1.json'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, separators=(',', ':'), ensure_ascii=False) + '\n')


def build():
    base = json.loads(BASE.read_text())
    plan = json.loads((ROOT / 'case-plan.json').read_text())
    rows = []
    for case in plan['cases']:
        suffix = case['case_id'].rsplit('__', 1)[-1]
        ref = case['reference_kind']
        paths = make_sources(SCRATCH / 'source-fixture' / suffix,
                             suffix, case['halt_requested'], ref)
        native_rows = [json.loads(line) for line in paths[1].read_text().splitlines()]
        source_dir = ROOT / 'selected-source' / suffix
        source_dir.mkdir(parents=True, exist_ok=True)
        geometry = source_dir / 'geometry.json'
        geometry.write_bytes(paths[3].read_bytes())
        source = {
            'path': 'geometry.json', 'source': str(geometry.relative_to(REPO)),
            'sha256': sha(geometry)}
        files = {name: value for name, value in base['files'].items()
                 if name not in ('pedestrian-caution-trace.jsonl',
                                 'pedestrian-source-review.jsonl',
                                 'context-survey.json', 'trace.jsonl',
                                 'capture/evidence.jsonl', 'video_frames.jsonl',
                                 'capture/manifest.json')}
        trace, evidence, frame_map = [], [], []
        for i, row in enumerate(native_rows):
            frame, time_s = row['native_frame'], row['time_s']
            center = row['front_x_m'] - 2
            speed = row['speed_mps']
            body = [[center + dx, dy, z] for dx, dy, z in
                    ((-2,-1,0),(-2,-1,1.5),(2,-1,0),(2,-1,1.5),
                     (2,1,0),(2,1,1.5),(-2,1,0),(-2,1,1.5))]
            trace.append({'frame': frame, 'time_s': time_s,
                          'position': {'x': center, 'y': 0, 'z': 1},
                          'position_m': [center, 0, 1], 'heading_deg': 0,
                          'speed_mps': speed, 'speed_mph': speed * 2.2369362921,
                          'control': {'throttle': .2 if speed else 0,
                                      'brake': 0 if speed else 1,
                                      'hand_brake': speed == 0},
                          'synthetic_diagnostic': True,
                          'velocity_mps': [speed, 0, 0],
                          'speed_provenance': 'synthetic_native_sample'})
            evidence.append({'original_frame': frame, 'replay_frame': frame,
                             'actor_id': 101, 'recording_time_s': time_s,
                             'replay_simulation_time_s': time_s,
                             'ego': {'position_m': [center, 0, 1],
                                     'heading_deg': 0, 'speed_mps': speed,
                                     'speed_provenance': 'synthetic_native_sample',
                                     'body_vertices_m': body},
                             'world': {'weather': {'cloudiness': 0, 'precipitation': 0,
                                                   'wetness': 0, 'fog_density': 0},
                                       'road_projection': {'road_id': 1, 'section_id': 0,
                                                           'lane_id': -1, 's_m': 100 + center}}})
            frame_map.append({'video_frame': i, 'carla_frame': frame,
                              'native_frame': frame, 'time_s': time_s,
                              'source_cameras': {name: frame for name in
                                                 ('overview', 'approach', 'reference_corner',
                                                  'driver_reference')}})
        def lines(values):
            return ''.join(json.dumps(row, separators=(',', ':'), allow_nan=False) + '\n'
                           for row in values)
        files['native.jsonl'] = paths[1].read_text()
        files['trace.jsonl'] = lines(trace)
        files['capture/evidence.jsonl'] = lines(evidence)
        files['video_frames.jsonl'] = lines(frame_map)
        manifest = {'extraction_confirmed': True, 'frames': 600,
                    'required_observations': [], 'synthetic_diagnostic': True,
                    'sources': {'trace.jsonl': hashlib.sha256(files['trace.jsonl'].encode()).hexdigest(),
                                'geometry.json': sha(geometry),
                                'road.xodr': hashlib.sha256(files['road.xodr'].encode()).hexdigest()}}
        files['capture/manifest.json'] = json.dumps(manifest, indent=2) + '\n'
        generator = {'files': files, 'graphs': base['graphs'], 'videos': base['videos']}
        generator_path = ROOT / ('selected-generator-' + suffix + '.json')
        write(generator_path, generator)
        recipe = {'format': 'worker-fixture-recipe', 'sources': [source],
                  'generator': {'source': str(generator_path.relative_to(REPO)),
                                'sha256': sha(generator_path)}}
        recipe_path = ROOT / ('selected-recipe-' + suffix + '.json')
        write(recipe_path, recipe)
        rows.append({'case_id': case['case_id'], 'generator': generator_path.name,
                     'generator_sha256': sha(generator_path), 'recipe': recipe_path.name,
                     'recipe_sha256': sha(recipe_path)})
        print(json.dumps({'case': suffix, 'generator_bytes': generator_path.stat().st_size}), flush=True)
    index = ROOT / 'selected-fixture-index.json'
    write(index, {'format': 'c111271-selected-fixtures-v1', 'cases': rows})
    return {'cases': len(rows), 'index_sha256': sha(index)}


if __name__ == '__main__':
    print(json.dumps(build()))
