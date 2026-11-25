"""Build three explicit five-frame synthetic compatibility source recipes."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
CAMERAS = (('overview', 1920, 1080), ('approach', 1280, 720),
           ('reference_corner', 1280, 720), ('driver_reference', 1280, 720))


def sha(value):
    return hashlib.sha256(value).hexdigest()


def encoded(value):
    return json.dumps(value, sort_keys=True, allow_nan=False) + '\n'


def lines(values):
    return ''.join(encoded(item) for item in values)


def build():
    plan = json.loads((HERE / 'case-plan.json').read_text())
    road = HERE / 'diagnostic-road.xodr'
    if not road.exists():
        raise ValueError('explicit synthetic road source required')
    recipes = []
    for case in plan['cases']:
        case_id = case['case_id']
        suffix = case_id.split('__')[-1]
        folder = HERE / 'cases' / suffix
        folder.mkdir(parents=True, exist_ok=True)
        source_hash = sha(road.read_bytes())
        source = {'case_id': case_id, 'start_xy': [0, 0],
                  'destination_xy': [10, 10],
                  'crossing_polygon': [[2, 2], [8, 2], [8, 8], [2, 8]],
                  'device_id': 'synthetic-diagonal-ped-1',
                  'source_sha256': {'map': source_hash,
                                    'device_inventory': sha(b'synthetic device inventory')},
                  'exception_484b_290_review': 'unresolved',
                  'source_kind': 'synthetic_software_fixture',
                  'official_status': 'not_verified'}
        walker = []
        device = []
        joins = []
        trace = []
        mapping = []
        evidence = []
        frames = []
        graphs = []
        for i in range(5):
            t = i / 20
            x = i * 2.5
            instruction = ('diagonal_dont_walk' if suffix == 'prohibitive_whole_crossing'
                           or (suffix == 'instruction_changes_during_crossing' and i >= 3)
                           else 'diagonal_walk')
            walker.append({'original_frame': i, 'time_s': t,
                           'walker_id': 7, 'center_xy': [x, x]})
            device.append({'original_frame': i, 'time_s': t,
                           'device_id': source['device_id'],
                           'source_sha256': source['source_sha256']['device_inventory'],
                           'pedestrian_governance': 'diagonal', 'instruction': instruction})
            joins.append({'frame': i, 'time_s': t, 'case_id': case_id,
                          'cameras': {name: {'frame': i, 'width': width,
                                             'height': height, 'pixel_format': 'bgra',
                                             'bytes': width * height * 4}
                                      for name, width, height in CAMERAS}})
            trace.append({'frame': i, 'time_s': t,
                          'position': {'x': x, 'y': x, 'z': 0.0},
                          'position_m': [x, x, 0.0], 'heading_deg': 45.0,
                          'speed_mps': 1.0, 'speed_mph': 1/.44704,
                          'velocity_mps': [1.0, 1.0, 0.0], 'control': {}})
            mapping.append({'video_frame': i, 'carla_frame': i,
                            'native_frame': i, 'time_s': t})
            observations = {'frame': i, 'time_s': t,
                            'map_context': {'declared_public_way_road_ids': []},
                            'participants': []}
            vertices = [[x + dx, x + dy, z]
                        for dx, dy in ((-.2, -.2), (.2, -.2), (.2, .2), (-.2, .2))
                        for z in (0.0, 1.8)]
            evidence.append({'actor_id': 7, 'ego': {'body_vertices_m': vertices,
                            'heading_deg': 45.0, 'position_m': [x, x, 0.0],
                            'speed_mps': 1.0,
                            'speed_provenance': 'synthetic_native_sample'},
                            'original_frame': i, 'original_observations': observations,
                            'recording_time_s': t, 'replay_frame': i,
                            'replay_simulation_time_s': t, 'world': {'weather': {}}})
            path = f'capture/native/graphs/base/{i:08d}.adapter.json'
            frames.append({'adapter_graph': f'graphs/base/{i:08d}.adapter.json',
                           'frame': i, 'simulation_time': t})
            graphs.append({'path': path,
                           'attributes': {'frame': i, 'time_s': t,
                                          'observed_evidence': observations},
                           'nodes': [], 'edges': []})
        files = {'diagonal-source.json': encoded(source),
                 'walker-diagonal.jsonl': lines(walker),
                 'device-diagonal.jsonl': lines(device),
                 'camera-frame-joins.jsonl': lines(joins),
                 'trace.jsonl': lines(trace),
                 'video_frames.jsonl': lines(mapping),
                 'capture/evidence.jsonl': lines(evidence),
                 'capture/native/frames.jsonl': lines(frames),
                 'capture/recorder_info.txt': 'Create 7: walker.pedestrian (synthetic diagnostic)\n',
                 'acquisition-provenance.json': encoded({
                     'provenance_kind': 'synthetic_fixture', 'diagnostic_fixture': True,
                     'scope': 'software-only; no physical or legal acceptance'})}
        files['capture/manifest.json'] = encoded({
            'acquisition': 'original_live_run', 'case_id': case_id,
            'complete_driving_lanes': False, 'extraction_confirmed': True,
            'frames': 5, 'status': 'draft',
            'sources': {'road.xodr': source_hash,
                        'trace.jsonl': sha(files['trace.jsonl'].encode())}})
        spec = {'files': files, 'graphs': graphs,
                'videos': [{'color': 'black', 'fps': 20, 'frames': 5,
                            'height': height, 'path': name + '.mkv', 'width': width}
                           for name, width, height in CAMERAS]}
        spec_path = folder / 'diagnostic.json'
        spec_path.write_text(json.dumps(spec, indent=2) + '\n')
        note = folder / 'diagnostic-source-note.json'
        note.write_text(encoded({'case_id': case_id,
                                 'source_kind': 'synthetic_software_fixture',
                                 'native_or_legal_acceptance_claimed': False}))
        recipe = {'format': 'worker-fixture-recipe', 'sources': [
            {'path': 'road.xodr', 'source': str(road.relative_to(REPO)),
             'sha256': source_hash},
            {'path': 'diagnostic-source-note.json',
             'source': str(note.relative_to(REPO)), 'sha256': sha(note.read_bytes())}],
            'generator': {'source': str(spec_path.relative_to(REPO)),
                          'sha256': sha(spec_path.read_bytes())}}
        recipe_path = folder / 'fixture-recipe.json'
        recipe_path.write_text(json.dumps(recipe, indent=2) + '\n')
        recipes.append(recipe_path)
    return recipes


if __name__ == '__main__':
    print('built', len(build()), 'explicit synthetic fixture recipes')
