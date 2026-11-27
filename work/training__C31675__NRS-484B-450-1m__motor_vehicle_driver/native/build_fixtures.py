"""Construct source-inventoried synthetic diagnostics for the exact bridge pair."""
import hashlib
import json
import os
from pathlib import Path

from geometry import DECK_POLYGON_XY_M, elevation, open_drive

HERE = Path(__file__).resolve().parent
ASSIGNMENT = HERE.parent
ROOT = ASSIGNMENT.parents[1]
AID = ASSIGNMENT.name
BASE = ROOT / 'work/training__C135709__NRS-484B-450-1o__motor_vehicle_driver/diagnostic-false.json'
CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')


def sha(value):
    return hashlib.sha256(value.encode()).hexdigest()


def lines(rows):
    return ''.join(json.dumps(row, separators=(',', ':'), allow_nan=False) + '\n' for row in rows)


def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    scratch = ROOT / '.runtime-work' / 'c31675-write'
    scratch.mkdir(parents=True, exist_ok=True)
    temporary = scratch / (sha(str(path)) + '.tmp')
    temporary.write_text(data)
    os.replace(temporary, path)


def box(x, y, z):
    return [[x + dx, y + dy, z + dz] for dx in (-2.0, 2.0)
            for dy in (-1.0, 1.0) for dz in (0.0, 2.0)]


def footprint(x, y):
    return [[x-2, y-1], [x+2, y-1], [x+2, y+1], [x-2, y+1]]


def main():
    baseline = json.loads(BASE.read_text())
    manifest_path = ASSIGNMENT / 'draft-execution-manifest.json'
    manifest = json.loads(manifest_path.read_text())
    proposal_cases = []
    for entry in manifest['cases']:
        suffix = entry['case_id'].rsplit('__', 1)[-1]
        end_x = -25.0 if suffix == 'false' else 50.0
        files = {key: value for key, value in baseline['files'].items() if key in (
            'capture/recorder_info.txt', 'capture/evidence.jsonl',
            'capture/native/frames.jsonl', 'capture/manifest.json',
            'trace.jsonl', 'video_frames.jsonl')}
        files['road.xodr'] = open_drive() + '\n'
        trace = [json.loads(line) for line in files['trace.jsonl'].splitlines()]
        mapping = [json.loads(line) for line in files['video_frames.jsonl'].splitlines()]
        evidence = [json.loads(line) for line in files['capture/evidence.jsonl'].splitlines()]
        frames = [json.loads(line) for line in files['capture/native/frames.jsonl'].splitlines()]
        graphs = json.loads(json.dumps(baseline['graphs']))
        bridge_rows = []
        for i in range(600):
            native = 1000 + i
            time = i / 20
            x = -75 + (end_x + 75) * min(i / 120, 1)
            z = elevation(x)
            speed = 0.0 if i >= 120 else (end_x + 75) / 6
            vertices = box(x, -1.75, z)
            position = [x, -1.75, z]
            other_position = [120.0, 1.75, elevation(120.0)]
            other_vertices = box(120.0, 1.75, elevation(120.0))
            trace[i].update(frame=native, time_s=time,
                position={'x': x, 'y': -1.75, 'z': z}, position_m=position,
                speed_mps=speed, speed_mph=speed * 2.2369362921,
                velocity_mps=[speed, 0, 0], control={'phase': 'approach' if i < 120 else 'hold'})
            mapping[i].update(video_frame=i, native_frame=native,
                carla_frame=native, time_s=time,
                camera_native_frames={camera: native for camera in CAMERAS})
            evidence[i].update(original_frame=native, replay_frame=native,
                recording_time_s=time, replay_simulation_time_s=time)
            evidence[i]['ego'].update(position_m=position, speed_mps=speed,
                                      body_vertices_m=vertices)
            evidence[i]['world']['road_projection'].update(road_id=1,
                lane_id=-1, s_m=x+100)
            observations = evidence[i]['original_observations']
            observations.update(frame=native, time_s=time)
            subject = next(p for p in observations['participants'] if p['actor_id'] == 205)
            subject.update(position_m=position, velocity_mps=[speed, 0, 0],
                           speed_mps=speed, body_vertices_m=vertices)
            other = {'actor_id': 206, 'blueprint': 'vehicle.lincoln.mkz_2020',
                     'position_m': other_position, 'heading_deg': 180,
                     'velocity_mps': [0, 0, 0], 'speed_mps': 0,
                     'body_vertices_m': other_vertices}
            observations['participants'] = [subject, other]
            frames[i]['simulation_time'] = time
            graph = graphs[i]
            graph['attributes']['observed_evidence'] = observations
            graph['nodes'][0]['attributes'].update(vertex=position,
                threedbbox=vertices, entity_id=205)
            graph['nodes'].append({'id': 'other_vehicle', 'attributes': {
                'vertex': other_position, 'sem_class': 'vehicle',
                'forward': [-1, 0, 0], 'entity_id': 206,
                'threedbbox': other_vertices}})
            bridge_rows.append({'frame': i, 'native_frame': native,
                'time_s': time, 'speed_mps': speed,
                'body_footprint_xy_m': footprint(x, -1.75),
                'requested_halt_cause': 'voluntary_destination',
                'other_actor_id': 206, 'other_position_xyz_m': other_position,
                'exception_verified': False})
        for name, rows in (('trace.jsonl', trace), ('video_frames.jsonl', mapping),
                           ('capture/evidence.jsonl', evidence),
                           ('capture/native/frames.jsonl', frames),
                           ('bridge-trace.jsonl', bridge_rows)):
            files[name] = lines(rows)
        files['bridge-map.json'] = json.dumps({
            'source_kind': 'native_bridge_lane_survey', 'structure_type': 'bridge',
            'deck_polygon_xy_m': DECK_POLYGON_XY_M,
            'native_lane_survey': [{'requested_x_m': x,
                'native_xyz_m': [x, -1.75, elevation(x)],
                'road_id': 1, 'lane_id': -1}
                for x in (-75, -25, 0, 50, 100, 175)],
            'physical_support_verified': False, 'original_pixels_verified': False,
            'diagnostic_fixture': True}, separators=(',', ':')) + '\n'
        files['fixture-provenance.json'] = json.dumps({
            'diagnostic_fixture': True, 'source': 'synthetic bridge and ground halt',
            'physical_acceptance_claimed': False}, separators=(',', ':')) + '\n'
        capture_manifest = json.loads(files['capture/manifest.json'])
        capture_manifest.update(case_id=entry['case_id'], frames=600,
            sources={'road.xodr': sha(files['road.xodr']),
                     'trace.jsonl': sha(files['trace.jsonl'])})
        files['capture/manifest.json'] = json.dumps(capture_manifest,
                                                      separators=(',', ':')) + '\n'
        source_root = ASSIGNMENT / 'diagnostic-source' / suffix
        sources = []
        for name, value in files.items():
            source = source_root / name
            write(source, value)
            sources.append({'path': name, 'source': str(source.relative_to(ROOT)),
                            'sha256': sha(value)})
        specification = {'files': {}, 'graphs': graphs,
            'videos': [{'path': camera + '.mkv', 'frames': 600,
                'width': 1920 if camera == 'overview' else 1280,
                'height': 1080 if camera == 'overview' else 720,
                'fps': 20, 'color': 'blue' if suffix == 'false' else 'green'}
                for camera in CAMERAS]}
        generator = ASSIGNMENT / ('diagnostic-generator-' + suffix + '.json')
        write(generator, json.dumps(specification, separators=(',', ':')) + '\n')
        recipe = {'format': 'worker-fixture-recipe', 'sources': sources,
            'generator': {'source': str(generator.relative_to(ROOT)),
                          'sha256': sha(generator.read_text())}}
        recipe_path = ASSIGNMENT / ('diagnostic-' + suffix + '-recipe.json')
        write(recipe_path, json.dumps(recipe, indent=2, sort_keys=True) + '\n')
        entry['fixture_recipe'] = str(recipe_path.relative_to(ROOT))
        proposal_cases.append({'case_id': entry['case_id'],
            'target_law_id': 'NRS-484B-450-1m', 'target_type': 'boundary_probe',
            'rationale': 'Measure original body overlap with bridge deck at rest; legal result unresolved',
            'recording_description': json.loads((ASSIGNMENT / entry['construction']).read_text())['recording_description'],
            'variable_assignments': {'stationary_footprint_on_bridge': {
                'kind': 'subject_behavior', 'value': None}},
            'unresolved_judgment_calls': ['stop, stand or park', 'upon any bridge',
                'necessary to avoid conflict', 'compliance with law or officer/device direction']})
    proposals = ASSIGNMENT / 'proposals' / 'cases.json'
    write(proposals, json.dumps({'cell_id': 'C31675', 'actor': 'motor_vehicle_driver',
        'status': 'draft', 'sweep_specs': [], 'sweeps_expanded': True,
        'cases': proposal_cases}, indent=2) + '\n')
    write(manifest_path, json.dumps(manifest, indent=2, sort_keys=True) + '\n')
    print(json.dumps({'case_ids': [e['case_id'] for e in manifest['cases']],
                      'source_files': sum(len(json.loads((ASSIGNMENT / (
                          'diagnostic-' + e['case_id'].rsplit('__',1)[-1] + '-recipe.json')).read_text())['sources'])
                          for e in manifest['cases']),
                      'diagnostic_only': True}))


if __name__ == '__main__':
    main()
