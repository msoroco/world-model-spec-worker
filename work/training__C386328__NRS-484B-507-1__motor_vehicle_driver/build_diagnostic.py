"""Build five synthetic source-shaped freight diagnostics, never original evidence."""
import copy
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import subprocess

from freight_scene import CASES, CAMERAS, scene_request

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
EXAMPLE = json.loads((REPO / 'runtime/fixtures/example.json').read_text())
VIEWS = (('overview', 1920, 1080), ('approach', 1280, 720),
         ('reference_corner', 1280, 720), ('driver_reference', 1280, 720))


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def put(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, separators=(',', ':'), ensure_ascii=False, allow_nan=False) + '\n')


def lines(path, items):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(''.join(json.dumps(item, separators=(',', ':'), allow_nan=False) + '\n'
                            for item in items))


def body(x, y, length=4.5, width=1.8):
    return [[x + dx * length / 2, y + dy * width / 2, z]
            for dx in (-1, 1) for dy in (-1, 1) for z in (0, 1.5)]


def video_hashes(scratch):
    scratch.mkdir(parents=True, exist_ok=True)
    result = {}
    for name, width, height in VIEWS:
        path = scratch / (name + '.mkv')
        if not path.is_file():
            subprocess.run(['ffmpeg', '-nostdin', '-hide_banner', '-loglevel', 'error', '-n',
                            '-f', 'lavfi', '-i', f'color=c=black:s={width}x{height}:r=20',
                            '-frames:v', '600', '-an', '-c:v', 'ffv1', '-threads', '1',
                            '-fflags', '+bitexact', '-flags:v', '+bitexact', str(path)],
                           check=True, timeout=300)
        result[name] = sha(path)
    return result


def build(slug, videos):
    scene = scene_request(slug)
    cid = HERE.name + '__' + slug
    root = HERE / 'diagnostic' / slug
    sources = root / 'sources'
    sources.mkdir(parents=True, exist_ok=True)
    (sources / 'road.xodr').write_text(scene['road_opendrive'].rstrip() + '\n')
    (sources / 'carla_recorder.log').write_text('Synthetic freight diagnostic; no Native recording.\n')
    (sources / 'capture/recorder_info.txt').parent.mkdir(parents=True, exist_ok=True)
    (sources / 'capture/recorder_info.txt').write_text(
        'Synthetic C386328 diagnostic; no Native recording.\n'
        'Create 205: vehicle.tesla.model3 (0) at (-32, -2.3, 0.5)\n')
    (sources / 'capture/native_map_facts.json').write_text(
        EXAMPLE['files']['capture/native_map_facts.json'].rstrip() + '\n')
    native_map_hash = sha(sources / 'road.xodr')
    intent = CASES[slug]
    within = list(range(120, 471))
    pickup = list(range(240, 301)) if intent['material'] == 'pickup_loading' else []
    passenger = list(range(170, 311)) if intent['passenger'] == 'loading' else []
    wait = list(range(160, 351)) if intent['waiting'] else []
    put(sources / 'zone-review.json', {
        'source_kind': 'independent_original_zone_review', 'diagnostic_fixture_only': True,
        'case_id': cid, 'reviewer': 'synthetic-zone-reviewer', 'full_interval_reviewed': True,
        'native_map_sha256': native_map_hash, 'zone_kind': 'freight_curb_loading',
        'zone_marking_source_id': 'synthetic-zone-marking',
        'regulatory_sign_source_id': 'synthetic-sign',
        'sign_hours_source_id': 'synthetic-sign-hours',
        'civil_time_source_id': 'synthetic-civil-clock',
        'effective_start_minute_local': 480, 'effective_end_minute_local': 1020,
        'vehicle_within_zone_frame_ids': within,
        'original_regulatory_authority_confirmed': False})
    civil = datetime(2026, 11, 23, 12 if intent['effective'] else 18,
                     tzinfo=timezone(timedelta(hours=-8)))
    base_trace = json.loads(EXAMPLE['files']['trace.jsonl'].splitlines()[0])
    base_evidence = json.loads(EXAMPLE['files']['capture/evidence.jsonl'].splitlines()[0])
    frames, freight, core, ego_body, material_body, passenger_body, waiting_body = [], [], [], [], [], [], []
    evidence, native_rows, graph_rows = [], [], []
    source_ego = next(node for node in EXAMPLE['graphs'][0]['nodes'] if node['id'] == 'ego')
    keep = ('vertex', 'sem_class', 'forward', 'right', 'up', 'entity_id',
            'threedbbox', 'carla_vel_x', 'carla_vel_y', 'carla_vel_z',
            'carla_speed', 'original_observation')
    ego_node = {'id': 'ego', 'attributes': {key: source_ego['attributes'][key] for key in keep}}
    for i in range(600):
        native = 800000 + i
        time_s = i / 20
        x = -32 + .27 * min(i, 120) + .15 * max(0, i - 470)
        speed = 5.4 if i < 120 else (0 if i <= 470 else 3)
        frame = {'video_frame': i, 'native_frame': native, 'carla_frame': native,
                 'time_s': time_s, 'source_cameras': {name: native for name in CAMERAS},
                 'camera_rgb_sha256': {name: hashlib.sha256((slug + name + str(i)).encode()).hexdigest()
                                       for name in CAMERAS}}
        frames.append(frame)
        material_xyz = [0, -6, .5] if i in pickup or (pickup and i > max(pickup)) else [0, -2.5, .5]
        passenger_y = -6 + 2.8 * min(1, max(0, (i - 170) / 140)) if passenger else -6
        freight.append({**frame, 'vehicle_id': 205, 'observed_speed_mps': speed,
                        'vehicle_xyz_m': [x, -2.3, .5], 'material_xyz_m': material_xyz,
                        'passenger_xyz_m': [0, passenger_y, .5] if passenger else None,
                        'waiting_vehicle_xyz_m': [-16, -2.3, .5] if wait else None,
                        'civil_timestamp': (civil + timedelta(seconds=time_s)).isoformat(),
                        'requested_material_activity': intent['material'],
                        'requested_passenger_activity': intent['passenger'],
                        'original_material_or_passenger_transfer_verified': False,
                        'original_interference_verified': False})
        ego_body.append({'native_frame': native, 'actor_id': 205,
                         'body_vertices_m': body(x, -2.3)})
        material_body.append({'native_frame': native, 'actor_id': 206,
                              'body_vertices_m': body(material_xyz[0], material_xyz[1], .5, .5)})
        passenger_body.append({'native_frame': native, 'actor_id': 207 if passenger else None,
                               'body_vertices_m': body(0, passenger_y, .5, .4) if passenger else None})
        waiting_body.append({'native_frame': native, 'actor_id': 208 if wait else None,
                             'body_vertices_m': body(-16, -2.3) if wait else None})
        trace = copy.deepcopy(base_trace)
        trace['frame'] = native
        trace['time_s'] = time_s
        trace['position_m'] = [x, -2.3, .5]
        trace['position'] = {'x': x, 'y': -2.3, 'z': .5}
        trace['velocity_mps'] = [speed, 0, 0]
        trace['speed_mps'] = speed
        trace['speed_mph'] = speed * 2.2369362921
        core.append(trace)
        obs = copy.deepcopy(base_evidence)
        obs['original_frame'] = native
        obs['replay_frame'] = native
        obs['recording_time_s'] = time_s
        obs['replay_simulation_time_s'] = time_s
        obs['ego']['position_m'] = [x, -2.3, .5]
        obs['ego']['speed_mps'] = speed
        obs['original_observations']['frame'] = native
        obs['original_observations']['time_s'] = time_s
        obs['original_observations']['participants'] = []
        obs['original_observations']['participant_inventory'] = []
        obs['original_observations']['rgb_sensors'] = [{'actor_id': 999,
            'blueprint': 'sensor.camera.rgb', 'diagnostic_fixture_only': True}]
        obs['original_observations']['world_settings']['no_rendering_mode'] = False
        evidence.append(obs)
        graph_rows.append({'path': f'capture/native/graphs/base/{native:09d}.adapter.json',
                           'attributes': {'frame': native, 'simulation_time_s': time_s,
                                          'observed_evidence': obs['original_observations'],
                                          'synthetic_diagnostic': True},
                           'nodes': [ego_node], 'edges': []})
        native_rows.append({'frame': native, 'time_s': time_s,
            'simulation_time': time_s, 'synthetic_diagnostic': True,
            'adapter_graph': f'graphs/base/{native:09d}.adapter.json'})
    for filename, values in (('freight_trace.jsonl', freight), ('video_frames.jsonl', frames),
                             ('trace.jsonl', core), ('ego_body.jsonl', ego_body),
                             ('material_body.jsonl', material_body),
                             ('passenger_body.jsonl', passenger_body),
                             ('waiting_body.jsonl', waiting_body),
                             ('capture/evidence.jsonl', evidence),
                             ('capture/native/frames.jsonl', native_rows)):
        lines(sources / filename, values)
    put(sources / 'activity-review.json', {
        'source_kind': 'independent_original_activity_review', 'diagnostic_fixture_only': True,
        'case_id': cid, 'reviewer': 'synthetic-activity-reviewer',
        'full_interval_reviewed': True, 'video_sha256': videos,
        'body_sha256': {name: sha(sources / name) for name in
                        ('ego_body.jsonl', 'material_body.jsonl',
                         'passenger_body.jsonl', 'waiting_body.jsonl')},
        'materials_vehicle_classification_source_id': 'synthetic-class-review',
        'passenger_identity_source_id': 'synthetic-passenger-review',
        'material_identity_source_id': 'synthetic-material-review',
        'pickup_loading_frame_ids': pickup, 'unloading_delivery_frame_ids': [],
        'passenger_loading_frame_ids': passenger, 'passenger_unloading_frame_ids': [],
        'materials_vehicle_waiting_frame_ids': wait,
        'materials_vehicle_about_to_enter_frame_ids': [],
        'original_interference_confirmed': False})
    put(sources / 'acquisition-provenance.json', {
        'provenance_kind': 'synthetic_fixture', 'diagnostic_fixture': True,
        'native_executed': False})
    manifest = json.loads(EXAMPLE['files']['capture/manifest.json'])
    manifest.update(case_id=cid, frames=600, required_observations=[],
                    source_run='synthetic:c386328-diagnostic-only',
                    extraction_confirmed=True,
                    sources={'road.xodr': sha(sources / 'road.xodr'),
                             'trace.jsonl': sha(sources / 'trace.jsonl'),
                             'carla_recorder.log': sha(sources / 'carla_recorder.log')})
    manifest['native_map_facts'] = {'path': 'native_map_facts.json',
                                    'sha256': sha(sources / 'capture/native_map_facts.json')}
    put(sources / 'capture/manifest.json', manifest)
    generator = {'files': {}, 'graphs': graph_rows,
                 'videos': [{'path': name + '.mkv', 'frames': 600, 'width': width,
                            'height': height, 'fps': 20, 'color': 'black'}
                           for name, width, height in VIEWS]}
    generator_path = HERE / ('selected-generator-' + slug + '.json')
    put(generator_path, generator)
    inventory = [{'path': str(path.relative_to(sources)),
                  'source': str(path.relative_to(REPO)), 'sha256': sha(path)}
                 for path in sorted(sources.rglob('*')) if path.is_file()]
    recipe = {'format': 'worker-fixture-recipe', 'sources': inventory,
              'generator': {'source': str(generator_path.relative_to(REPO)),
                            'sha256': sha(generator_path)}}
    recipe_path = HERE / ('selected-recipe-' + slug + '.json')
    put(recipe_path, recipe)
    return {'case_id': cid, 'sources': len(inventory),
            'largest_source_bytes': max((sources / item['path']).stat().st_size for item in inventory)}


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--scratch', required=True)
    args = parser.parse_args()
    hashes = video_hashes(Path(args.scratch))
    print(json.dumps([build(slug, hashes) for slug in CASES], sort_keys=True))
