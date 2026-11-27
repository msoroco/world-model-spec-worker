"""Create explicitly synthetic, source-shaped four-case compatibility fixtures."""
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys

from crosswalk_pass_scene import CASES, request
from prove_crosswalk_pass import trace

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
EXAMPLE = json.loads((REPO / 'runtime/fixtures/example.json').read_text())
VIEWS = (('overview', 1920, 1080), ('approach', 1280, 720),
         ('reference_corner', 1280, 720), ('driver_reference', 1280, 720))


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def put(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, separators=(',', ':'), allow_nan=False) + '\n')


def lines(path, values):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(''.join(json.dumps(v, separators=(',', ':'), allow_nan=False) + '\n' for v in values))


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
    cid = HERE.name + '__' + slug
    root = HERE / 'diagnostic' / slug
    sources = root / 'sources'
    sources.mkdir(parents=True, exist_ok=True)
    scene = request(slug)
    (sources / 'road.xodr').write_text(scene['road_opendrive'].rstrip() + '\n')
    (sources / 'carla_recorder.log').write_text('Synthetic crosswalk diagnostic; no Native recording.\n')
    (sources / 'capture/recorder_info.txt').parent.mkdir(parents=True, exist_ok=True)
    (sources / 'capture/recorder_info.txt').write_text('Synthetic C146108 diagnostic; no Native recording.\nCreate 205: vehicle.tesla.model3 (0) at (-40, -1.75, 0.5)\n')
    (sources / 'capture/native_map_facts.json').write_text(EXAMPLE['files']['capture/native_map_facts.json'].rstrip() + '\n')
    native_map_hash = sha(sources / 'road.xodr')
    kind = 'unmarked_intersection' if slug.startswith('unmarked') else 'marked'
    put(sources / 'crosswalk-review.json', {
        'source_kind': 'independent_original_crosswalk_review', 'diagnostic_fixture_only': True,
        'case_id': cid, 'reviewer': 'synthetic-crossing-reviewer', 'full_interval_reviewed': True,
        'native_map_sha256': native_map_hash, 'crosswalk_kind': kind,
        'intersection_source_id': 'synthetic-junction-reference',
        'crosswalk_reference_source_id': 'synthetic-crossing-reference',
        'intersection_crossing_sourced': kind == 'unmarked_intersection',
        'same_direction_rear_approach': True,
        'crosswalk_near_x_m': -2, 'crosswalk_far_x_m': 2})
    rows = trace(slug)
    base_trace = json.loads(EXAMPLE['files']['trace.jsonl'].splitlines()[0])
    base_evidence = json.loads(EXAMPLE['files']['capture/evidence.jsonl'].splitlines()[0])
    ego_base = next(node for node in EXAMPLE['graphs'][0]['nodes'] if node['id'] == 'ego')
    keep = ('vertex', 'sem_class', 'forward', 'right', 'up', 'entity_id',
            'threedbbox', 'carla_vel_x', 'carla_vel_y', 'carla_vel_z',
            'carla_speed', 'original_observation')
    ego_node = {'id': 'ego', 'attributes': {key: ego_base['attributes'][key] for key in keep}}
    frame_rows, core_rows, evidence_rows, native_rows, graph_rows = [], [], [], [], []
    ego_body, lead_body, ped_body = [], [], []
    for i, row in enumerate(rows):
        native = row['native_frame']
        frame = {k: row[k] for k in ('video_frame', 'native_frame', 'time_s', 'source_cameras')}
        frame['carla_frame'] = native
        frame['camera_rgb_sha256'] = {name: hashlib.sha256((slug + name + str(i)).encode()).hexdigest() for name, _, _ in VIEWS}
        frame_rows.append(frame)
        row.update(frame)
        ego_body.append({'native_frame': native, 'actor_id': 205, 'body_vertices_m': body(row['ego_x_m'], row['ego_y_m'])})
        lead_body.append({'native_frame': native, 'actor_id': 206, 'body_vertices_m': body(-6, -1.75)})
        ped_body.append({'native_frame': native, 'actor_id': 207, 'body_vertices_m': body(0, row['pedestrian_y_m'], .4, .4)})
        core = copy.deepcopy(base_trace)
        core['frame'] = native
        core['time_s'] = i / 20
        core['position_m'] = [row['ego_x_m'], row['ego_y_m'], .5]
        core['position'] = {'x': row['ego_x_m'], 'y': row['ego_y_m'], 'z': .5}
        core['velocity_mps'] = [0, 0, 0]
        core['speed_mps'] = 0
        core['speed_mph'] = 0
        core_rows.append(core)
        obs = copy.deepcopy(base_evidence)
        obs['original_frame'] = native
        obs['replay_frame'] = native
        obs['recording_time_s'] = i / 20
        obs['replay_simulation_time_s'] = i / 20
        obs['ego']['position_m'] = [row['ego_x_m'], row['ego_y_m'], .5]
        obs['ego']['speed_mps'] = 0
        orig = obs['original_observations']
        orig['frame'] = native
        orig['time_s'] = i / 20
        orig['participants'] = []
        orig['participant_inventory'] = []
        orig['rgb_sensors'] = [{'actor_id': 999, 'blueprint': 'sensor.camera.rgb', 'diagnostic_fixture_only': True}]
        orig['world_settings']['no_rendering_mode'] = False
        evidence_rows.append(obs)
        native_rows.append({'frame': native, 'time_s': i / 20,
                            'simulation_time': i / 20, 'synthetic_diagnostic': True,
                            'adapter_graph': f'graphs/base/{native:09d}.adapter.json'})
        graph_rows.append({'path': f'capture/native/graphs/base/{native:09d}.adapter.json',
                           'attributes': {'frame': native, 'simulation_time_s': i / 20,
                                          'observed_evidence': orig, 'synthetic_diagnostic': True},
                           'nodes': [ego_node], 'edges': []})
    for name, values in (('crosswalk_trace.jsonl', rows), ('video_frames.jsonl', frame_rows),
                         ('trace.jsonl', core_rows), ('ego_body.jsonl', ego_body),
                         ('lead_body.jsonl', lead_body), ('pedestrian_body.jsonl', ped_body),
                         ('capture/evidence.jsonl', evidence_rows),
                         ('capture/native/frames.jsonl', native_rows)):
        lines(sources / name, values)
    put(sources / 'purpose-review.json', {
        'source_kind': 'independent_original_stop_purpose_review', 'diagnostic_fixture_only': True,
        'case_id': cid, 'reviewer': 'synthetic-purpose-reviewer', 'full_interval_reviewed': True,
        'video_sha256': videos,
        'body_sha256': {name: sha(sources / name) for name in ('ego_body.jsonl', 'lead_body.jsonl', 'pedestrian_body.jsonl')},
        'lead_stopped_for_pedestrian_sourced': True,
        'lead_stop_purpose_source_id': 'synthetic-purpose-source',
        'pedestrian_crossing_source_id': 'synthetic-pedestrian-source',
        'lead_center_x_m': -6})
    put(sources / 'acquisition-provenance.json', {'provenance_kind': 'synthetic_fixture',
        'diagnostic_fixture': True, 'native_executed': False})
    manifest = json.loads(EXAMPLE['files']['capture/manifest.json'])
    manifest.update(case_id=cid, frames=600, required_observations=[],
                    source_run='synthetic:c146108-diagnostic-only', extraction_confirmed=True,
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
    gp = HERE / ('selected-generator-' + slug + '.json')
    put(gp, generator)
    inventory = [{'path': str(path.relative_to(sources)),
                  'source': str(path.relative_to(REPO)), 'sha256': sha(path)}
                 for path in sorted(sources.rglob('*')) if path.is_file()]
    recipe = {'format': 'worker-fixture-recipe', 'sources': inventory,
              'generator': {'source': str(gp.relative_to(REPO)), 'sha256': sha(gp)}}
    rp = HERE / ('selected-recipe-' + slug + '.json')
    put(rp, recipe)
    return {'case_id': cid, 'sources': len(inventory),
            'largest_source_bytes': max((sources / item['path']).stat().st_size for item in inventory)}


if __name__ == '__main__':
    print(json.dumps([build(slug, video_hashes(Path(sys.argv[1]))) for slug in CASES], sort_keys=True))
