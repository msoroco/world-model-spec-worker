"""Bind a synthetic saved-source fixture to original example frame identities.

The example is a software diagnostic, not a speed/condition observation from
CARLA. The resulting sample values are deliberately not target attainment.
"""

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[1]
EXAMPLE = REPO / 'runtime/fixtures/example.json'


def _rows(text):
    return [json.loads(line) for line in text.splitlines() if line.strip()]


def build():
    spec = json.loads(EXAMPLE.read_text())
    config = json.loads((ROOT / 'config.json').read_text())
    surface = (ROOT / 'surface.txt').read_text()
    surface_source = {'path': 'surface.txt',
                      'sha256': hashlib.sha256(surface.encode()).hexdigest()}
    ctx = {'native_map_id': 'diagnostic-example-map', 'ego_actor_id': 205,
           'road_id': 7, 'lane_id': -1, 'road_surface_source': surface_source,
           'lane_width_source': 'synthetic diagnostic waypoint',
           'traffic_source': 'synthetic diagnostic lead',
           'weather_source': 'synthetic diagnostic weather',
           'sight_source': 'synthetic diagnostic ray',
           'curvature_source': 'synthetic diagnostic waypoint',
           'braking_model_source': 'declared diagnostic engineering model',
           'diagnostic_reaction_time_s': 1.0,
           'diagnostic_braking_deceleration_mps2': 5.0,
           'legal_threshold_claimed': False}
    spec['files']['road_context.json'] = json.dumps(ctx, indent=2) + '\n'
    trace = _rows(spec['files']['trace.jsonl'])
    frame_map = _rows(spec['files']['video_frames.jsonl'])
    if len(trace) != len(frame_map) or len(trace) < 2:
        raise ValueError('Original diagnostic frame inventory changed')
    history = []
    for row, frame in zip(trace, frame_map):
        if row['frame'] != frame['carla_frame'] or row['time_s'] != frame['time_s']:
            raise ValueError('Original diagnostic frame identity changed')
        history.append({'frame': row['frame'], 'time_s': row['time_s'],
                        'ego_actor_id': 205, 'ego_position_m': row['position_m'],
                        'road_id': 7, 'lane_id': -1,
                        'ego_velocity_source': 'actor.get_velocity',
                        'ego_velocity_mps': row['velocity_mps'],
                        'lane_width_m': 3.5, 'surface': 'dry',
                        'surface_source': surface_source,
                        'physical_surface_verified': False,
                        'precipitation_percent': 0,
                        'weather_source': 'world.get_weather',
                        'sight_distance_m': 80,
                        'sight_ray_source': 'synthetic diagnostic ray',
                        'curvature_per_m': 0,
                        'curvature_source': 'synthetic diagnostic waypoint',
                        'surrounding_traffic': [{
                            'actor_id': 206, 'velocity_source': 'actor.get_velocity',
                            'velocity_mps': [0, 0, 0],
                            'longitudinal_body_gap_m': 20}]})
    spec['files']['condition_history.jsonl'] = ''.join(
        json.dumps(row, allow_nan=False) + '\n' for row in history)
    manifest = json.loads(spec['files']['capture/manifest.json'])
    manifest['case_id'] = config['selected_case_id']
    spec['files']['capture/manifest.json'] = json.dumps(manifest, indent=2) + '\n'
    destination = ROOT / 'diagnostic.json'
    destination.write_text(json.dumps(spec, separators=(',', ':'), allow_nan=False) + '\n')
    if destination.stat().st_size >= 2 * 1024 * 1024:
        raise ValueError('Returned diagnostic exceeds text size limit')
    source = destination.relative_to(REPO).as_posix()
    digest = hashlib.sha256(destination.read_bytes()).hexdigest()
    recipe = {'format': 'worker-fixture-recipe',
              'sources': [{'path': 'diagnostic-input.json', 'source': source,
                           'sha256': digest}],
              'generator': {'source': source, 'sha256': digest}}
    (ROOT / 'fixture-recipe.json').write_text(json.dumps(recipe, indent=2) + '\n')
    return {'diagnostic': source, 'sha256': digest,
            'frames': len(history), 'synthetic_fixture': True}


if __name__ == '__main__':
    print(json.dumps(build(), indent=2))
