"""Synthetic six-case CPU fixtures; these never constitute original evidence."""
import hashlib
import json
import math
from pathlib import Path

from signal_scene import CASE_SUFFIXES, request


HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')


def encode(value):
    return json.dumps(value, indent=2, allow_nan=False) + '\n'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def put(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(encode(value))


def lines(path, values):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(''.join(json.dumps(row, separators=(',', ':'),
        allow_nan=False) + '\n' for row in values))


def body(x, y):
    return [[x + dx, y + dy, z] for dx in (-2, 2)
        for dy in (-.9, .9) for z in (0, 1.5)]


def longitudinal_step(distance, onset):
    """Choose diagnostic x progress so the sampled curved path hits the boundary."""
    target = distance * .3048
    lo, hi = .01, 1.0
    for _ in range(70):
        mid = (lo + hi) / 2
        path = (460 - onset) * mid + 20 * (mid * mid + .175 * .175) ** .5
        if path < target:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def build(suffix):
    case_id = HERE.name + '__' + suffix
    out = HERE / 'fixture-source' / suffix
    out.mkdir(parents=True, exist_ok=True)
    plan = request(suffix)
    distance = plan['requested_signal_distance_ft']
    right = plan['signal_side'] == 'right'
    start_y, end_y = (-1.75, -5.25) if right else (-5.25, -1.75)
    initial_lane, end_lane = (-1, -2) if right else (-2, -1)
    onset = round(480 - distance * .3048 / .25)
    step = longitudinal_step(distance, onset)
    signals, bodies, trace, mapping, evidence, graphs, frames = [], [], [], [], [], [], []
    odometer = 0.0
    previous_xy = None
    for i in range(600):
        x = -90 + i * step
        lane_progress = max(0, min(1, (i - 460) / 20))
        y = start_y + (end_y - start_y) * lane_progress
        if previous_xy is not None:
            odometer += math.hypot(x - previous_xy[0], y - previous_xy[1])
        previous_xy = (x, y)
        lane = initial_lane if i < 480 else end_lane
        vertices = body(x, y)
        t = i / 20
        signal_on = i >= onset and not (plan['interruption_requested'] and
            onset + 12 <= i < onset + 18)
        signal = {'frame': i, 'original_carla_frame': i, 'time_s': t,
            'original_time_s': t, 'ego_xy_m': [x, y], 'native_yaw_deg': 0,
            'native_lane_id': lane, 'observed_odometer_m': odometer,
            'turn_indicator': plan['signal_side'] if signal_on else 'off',
            'course_change': i == 480, 'signal_requested': signal_on,
            'lane_change_requested': i >= 480,
            'source_kind': 'synthetic_fixture',
            'visible_signal_pixels_reviewed': False}
        signals.append(signal)
        bodies.append({'frame': i, 'time_s': t, 'body_vertices_m': vertices,
            'lane_id': lane, 'heading_deg': 0})
        trace.append({'frame': i, 'time_s': t, 'position': {'x': x, 'y': y, 'z': .75},
            'position_m': [x, y, .75], 'heading_deg': 0,
            'velocity_mps': [step * 20, 0, 0], 'speed_mps': step * 20,
            'speed_mph': step * 20 / .44704,
            'control': {'throttle': .2, 'brake': 0, 'hand_brake': False}})
        mapping.append({'video_frame': i, 'native_frame': i,
            'carla_frame': i, 'time_s': t})
        evidence.append({'original_frame': i, 'replay_frame': i,
            'recording_time_s': t, 'replay_simulation_time_s': t, 'actor_id': 107,
            'ego': {'body_vertices_m': vertices, 'heading_deg': 0,
                'position_m': [x, y, .75], 'speed_mps': step * 20,
                'speed_provenance': 'synthetic_native_sample'},
            'world': {'road_projection': {'lane_id': lane, 'road_id': 1,
                's_m': x + 100, 'section_id': 0},
                'weather': {'cloudiness': 80 if plan['weather_requested'] == 'rain' else 0,
                    'fog_density': 0, 'precipitation': 80 if plan['weather_requested'] == 'rain' else 0,
                    'wetness': 80 if plan['weather_requested'] == 'rain' else 0}}})
        graph_path = f'capture/native/graphs/base/{i:08d}.adapter.json'
        graphs.append({'path': graph_path, 'attributes': {'frame': i,
            'simulation_time_s': t, 'source': 'C245490 CPU diagnostic',
            'synthetic_diagnostic': True}, 'edges': [],
            'nodes': [{'id': 'ego', 'attributes': {'entity_id': 107,
                'forward': [1, 0, 0], 'sem_class': 'ego',
                'threedbbox': vertices, 'vertex': [x, y, .75]}}]})
        frames.append({'frame': i, 'simulation_time': t,
            'adapter_graph': graph_path.removeprefix('capture/native/'),
            'base': graph_path.removeprefix('capture/native/'),
            'nodes': 1, 'edges': 0})
    for name, values in (('signal-source.jsonl', signals),
            ('body_history.jsonl', bodies), ('trace.jsonl', trace),
            ('video_frames.jsonl', mapping), ('capture/evidence.jsonl', evidence)):
        lines(out / name, values)
    put(out / 'lane-source.json', {'lanes': [{'lane_id': -1, 'y_m': -1.75},
        {'lane_id': -2, 'y_m': -5.25}], 'public_highway_verified': False})
    put(out / 'area-source.json', {'area_class_requested': plan['area_class_requested'],
        'area_class_originally_verified': False,
        'district_or_other_original_authority': None,
        'weather_requested': plan['weather_requested'],
        'weather_originally_reviewed': False})
    put(out / 'acquisition-provenance.json', {'provenance_kind': 'synthetic_fixture',
        'diagnostic_fixture': True, 'original_native_observed': False})
    put(out / 'capture/manifest.json', {'extraction_confirmed': True,
        'frames': 600, 'synthetic_diagnostic': True,
        'sources': {'road.xodr': sha(HERE / 'road.xodr'),
            'trace.jsonl': sha(out / 'trace.jsonl')}})
    spec = {'files': {'capture/native/frames.jsonl': ''.join(
        json.dumps(row, separators=(',', ':')) + '\n' for row in frames),
        'capture/recorder_info.txt': 'synthetic CPU diagnostic; no CARLA recorder\nCreate 107: vehicle.tesla.model3 (0)\n'},
        'graphs': graphs,
        'videos': [{'path': name + '.mkv', 'width': 1920 if name == 'overview' else 1280,
            'height': 1080 if name == 'overview' else 720, 'fps': 20,
            'frames': 600, 'color': 'black'} for name in CAMERAS]}
    spec_path = HERE / ('fixture-spec-' + suffix + '.json')
    spec_path.write_text(encode(spec))
    names = ('signal-source.jsonl', 'body_history.jsonl', 'trace.jsonl',
        'video_frames.jsonl', 'capture/evidence.jsonl', 'capture/manifest.json',
        'lane-source.json', 'area-source.json', 'acquisition-provenance.json')
    recipe = {'format': 'worker-fixture-recipe',
        'generator': {'source': str(spec_path.relative_to(REPO)),
            'sha256': sha(spec_path)},
        'sources': [{'path': name, 'sha256': sha(out / name),
            'source': str((out / name).relative_to(REPO))} for name in names]}
    recipe_path = HERE / ('selected-recipe-' + suffix + '.json')
    recipe_path.write_text(encode(recipe))
    return recipe_path


if __name__ == '__main__':
    print('\n'.join(str(build(suffix).relative_to(REPO)) for suffix in CASE_SUFFIXES))
