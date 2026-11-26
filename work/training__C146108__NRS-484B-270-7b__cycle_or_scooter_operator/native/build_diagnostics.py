"""Build bounded source-shaped CPU recipes for three selected pass cases."""
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[1]
CAMERAS = (('overview', 1920, 1080), ('approach', 1280, 720),
           ('reference_corner', 1280, 720), ('driver_reference', 1280, 720))
CASES = ('bicycle_pass_wide', 'electric_bicycle_pass_wide',
         'electric_bicycle_pass_narrow')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, separators=(',', ':'), ensure_ascii=False) + '\n')


def lines(path, values):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('\n'.join(json.dumps(value, separators=(',', ':')) for value in values) + '\n')


def body(x, y, length, width):
    return [[round(x + dx, 5), round(y + dy, 5), z]
            for dx in (-length / 2, length / 2)
            for dy in (-width / 2, width / 2) for z in (0, 1.8)]


def build(suffix, candidate='primary'):
    family = 'draft-bicycle' if suffix.startswith('bicycle') else 'draft-ebike'
    bundle = json.loads((ROOT / family / suffix / candidate / 'construction.json').read_text())
    config = json.loads(next(f['content'] for f in bundle['files'] if f['path'] == 'config.json'))
    folder = ROOT / 'diagnostic' / suffix
    if candidate != 'primary':
        folder = folder / candidate
    sources = folder / 'sources'
    sys.path.insert(0, str(ROOT / 'native'))
    if suffix.startswith('bicycle'):
        from geometry import open_drive
    else:
        from geometry_ebike import open_drive
    (sources / 'road.xodr').parent.mkdir(parents=True, exist_ok=True)
    (sources / 'road.xodr').write_text(open_drive() + '\n')
    electric = config['rider_class'] == 'electric_bicycle'
    context = {'case_id': config['case_id'], 'rider_class': config['rider_class'],
        'passed_class': 'motor_vehicle', 'rider_dimensions_m': [1.2, .8],
        'motor_dimensions_m': [4, 2], 'motor_occupant_count': 1,
        'source_kind': 'generated_software_diagnostic',
        'original_native_classification_verified': False}
    if electric:
        context['rider_qualification'] = {'wheels': 2, 'operable_pedals': True,
            'saddle': True, 'motor_rated_watts': 500,
            'assist_only_while_pedaling': True, 'assist_cutoff_mph': 20,
            'moped': False, 'electric_scooter': False,
            'source': 'authored Class 1 generated diagnostic controller'}
    write(sources / 'pass-context.json', context)
    poses, trace, mapped, evidence, frames, graphs = [], [], [], [], [], []
    rider_y = config.get('rider_y_m', -1.75)
    for index in range(600):
        frame = 1000 + index
        t = round(index / 20, 5)
        rider_x = round(-50 + .16 * index, 5)
        motor_x = round(-30 + .04 * index, 5)
        rider = [rider_x, rider_y]
        motor = [motor_x, -5.25]
        pose = {'video_frame': index, 'native_frame': frame, 'time_s': t,
            'rider_xy_m': rider, 'motor_xy_m': motor,
            'rider_actor_id': 101, 'motor_actor_id': 202,
            'rider_body_xy_m': [v[:2] for v in body(rider_x, rider_y, 1.2, .8)[::2]],
            'motor_body_xy_m': [v[:2] for v in body(motor_x, -5.25, 4, 2)[::2]],
            'rider_speed_mps': 3.2, 'motor_speed_mps': .8,
            'synthetic_diagnostic': True}
        if electric:
            pose['drivetrain_command'] = {'pedaling': True,
                'pedal_cadence_rpm': 70, 'assist_power_watts': 500,
                'speed_mps': 3.2, 'assist_cutoff_mps': 20 * .44704,
                'power_source': 'authored generated diagnostic controller'}
        pose['frame'] = frame
        poses.append(pose)
        trace.append({'frame': frame, 'time_s': t,
            'position': {'x': rider_x, 'y': rider_y, 'z': 1},
            'position_m': [rider_x, rider_y, 1], 'heading_deg': 0,
            'speed_mps': 3.2, 'speed_mph': 3.2 / .44704,
            'velocity_mps': [3.2, 0, 0],
            'control': {'diagnostic': True}})
        mapped.append({'video_frame': index, 'carla_frame': frame,
            'native_frame': frame, 'time_s': t,
            'camera_native_frames': {name: frame for name, _, _ in CAMERAS}})
        evidence.append({'actor_id': 101,
            'ego': {'body_vertices_m': body(rider_x, rider_y, 1.2, .8),
                    'heading_deg': 0, 'position_m': [rider_x, rider_y, 1],
                    'speed_mps': 3.2,
                    'speed_provenance': 'synthetic_native_sample',
                    'synthetic_diagnostic': True},
            'original_frame': frame, 'other_actors': [],
            'recording_time_s': t, 'replay_frame': frame,
            'replay_simulation_time_s': t,
            'world': {'road_projection': {'lane_id': -1 if rider_y > -3.5 else -2,
                'road_id': 1, 's_m': rider_x + 100, 'section_id': 0},
                'weather': {'cloudiness': 0, 'fog_density': 0,
                    'precipitation': 0, 'wetness': 0}}})
        relative = f'graphs/base/{index:08d}.adapter.json'
        frames.append({'adapter_graph': relative, 'base': relative,
            'edges': 0, 'frame': frame, 'nodes': 1, 'simulation_time': t})
        graphs.append({'path': 'capture/native/' + relative,
            'attributes': {'frame': frame, 'simulation_time_s': t,
                'source': 'C146108 controlled pass CPU diagnostic',
                'synthetic_diagnostic': True},
            'edges': [], 'nodes': [{'id': 'ego', 'attributes': {
                'entity_id': 101, 'forward': [1, 0, 0], 'sem_class': 'ego',
                'threedbbox': body(rider_x, rider_y, 1.2, .8),
                'vertex': [rider_x, rider_y, 1]}}]})
    for name, rows in (('participant-poses.jsonl', poses), ('trace.jsonl', trace),
                       ('video_frames.jsonl', mapped), ('capture/evidence.jsonl', evidence)):
        lines(sources / name, rows)
    write(sources / 'capture/manifest.json', {'extraction_confirmed': True,
        'frames': 600, 'synthetic_diagnostic': True,
        'sources': {name: sha(sources / name) for name in
                    ('participant-poses.jsonl', 'pass-context.json',
                     'road.xodr', 'trace.jsonl')}})
    spec = {'files': {'capture/native/frames.jsonl': '\n'.join(
        json.dumps(row, separators=(',', ':')) for row in frames) + '\n',
        'capture/recorder_info.txt':
            'Synthetic diagnostic; no Native recording.\nCreate 101: vehicle.bh.crossbike (0)\n'},
        'graphs': graphs,
        'videos': [{'path': name + '.mkv', 'frames': 600,
            'width': width, 'height': height, 'fps': 20, 'color': 'black'}
            for name, width, height in CAMERAS]}
    write(folder / 'fixture-spec.json', spec)
    recipe = {'format': 'worker-fixture-recipe',
        'generator': {'source': str((folder / 'fixture-spec.json').relative_to(REPO)),
                      'sha256': sha(folder / 'fixture-spec.json')},
        'sources': [{'path': str(path.relative_to(sources)),
                     'source': str(path.relative_to(REPO)), 'sha256': sha(path)}
                    for path in sorted(sources.rglob('*')) if path.is_file()]}
    write(folder / 'fixture-recipe.json', recipe)
    return {'case': suffix, 'candidate': candidate, 'recipe_sha256': sha(folder / 'fixture-recipe.json'),
            'sources': len(recipe['sources']), 'frames': 600}


if __name__ == '__main__':
    outputs = [build(case) for case in CASES]
    outputs.extend(build(case, 'fallback1') for case in CASES
                   if (ROOT / ('draft-bicycle' if case.startswith('bicycle') else 'draft-ebike') /
                       case / 'fallback1/construction.json').is_file())
    print(json.dumps(outputs, sort_keys=True))
