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


SUFFIXES = ('dry_open_traffic', 'dry_4mps', 'dry_6mps', 'wet_same_traffic',
            'narrow_same_traffic', 'dense_traffic', 'low_visibility', 'ice_or_snow')


def build(suffix='dry_open_traffic'):
    spec = json.loads(EXAMPLE.read_text())
    if suffix == 'dry_open_traffic':
        config = json.loads((ROOT / 'config.json').read_text())
        surface_file = ROOT / 'surface.txt'
        destination = ROOT / 'diagnostic.json'
        recipe_file = ROOT / 'fixture-recipe.json'
    else:
        construction = json.loads((ROOT / 'cases' / (suffix + '-construction.json')).read_text())
        config = json.loads(next(row['content'] for row in construction['files']
                                 if row['path'] == 'config.json'))
        surface_file = ROOT / 'cases' / (suffix + '-surface.txt')
        destination = ROOT / 'cases' / (suffix + '-diagnostic.json')
        recipe_file = ROOT / 'cases' / (suffix + '-fixture-recipe.json')
    surface = surface_file.read_text()
    surface_source = {'path': 'surface.txt',
                      'sha256': hashlib.sha256(surface.encode()).hexdigest()}
    target = config['condition_target']
    def midpoint(name, default):
        interval = target.get(name)
        return (interval[0] + interval[1]) / 2 if interval else default
    road_id = 8 if suffix == 'narrow_same_traffic' else 7
    ctx = {'native_map_id': 'diagnostic-example-map', 'ego_actor_id': 205,
           'road_id': road_id, 'lane_id': -1, 'road_surface_source': surface_source,
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
                        'road_id': road_id, 'lane_id': -1,
                        'ego_velocity_source': 'actor.get_velocity',
                        'ego_velocity_mps': row['velocity_mps'],
                        'lane_width_m': midpoint('lane_width_m', 3.5),
                        'surface': target['surface'],
                        'surface_source': surface_source,
                        'physical_surface_verified': False,
                        'precipitation_percent': midpoint('precipitation_percent', 0),
                        'fog_density_percent': midpoint('fog_density_percent', 0),
                        'fog_distance_m': midpoint('fog_distance_m', 100),
                        'weather_source': 'world.get_weather',
                        'sight_distance_m': midpoint('sight_distance_m', 80),
                        'sight_ray_source': 'synthetic diagnostic ray',
                        'curvature_per_m': 0,
                        'curvature_source': 'synthetic diagnostic waypoint',
                        'surrounding_traffic': [{
                            'actor_id': 206, 'velocity_source': 'actor.get_velocity',
                            'velocity_mps': [0, 0, 0],
                            'longitudinal_body_gap_m': midpoint('longitudinal_body_gap_m', 20)}]})
    spec['files']['condition_history.jsonl'] = ''.join(
        json.dumps(row, allow_nan=False) + '\n' for row in history)
    manifest = json.loads(spec['files']['capture/manifest.json'])
    manifest['case_id'] = config['selected_case_id']
    spec['files']['capture/manifest.json'] = json.dumps(manifest, indent=2) + '\n'
    destination.write_text(json.dumps(spec, separators=(',', ':'), allow_nan=False) + '\n')
    if destination.stat().st_size >= 2 * 1024 * 1024:
        raise ValueError('Returned diagnostic exceeds text size limit')
    source = destination.relative_to(REPO).as_posix()
    digest = hashlib.sha256(destination.read_bytes()).hexdigest()
    surface_path = surface_file.relative_to(REPO).as_posix()
    recipe = {'format': 'worker-fixture-recipe',
              'sources': [{'path': 'diagnostic-input.json', 'source': source,
                           'sha256': digest},
                          {'path': 'surface.txt', 'source': surface_path,
                           'sha256': hashlib.sha256(surface_file.read_bytes()).hexdigest()}],
              'generator': {'source': source, 'sha256': digest}}
    recipe_file.write_text(json.dumps(recipe, indent=2) + '\n')
    return {'diagnostic': source, 'sha256': digest,
            'frames': len(history), 'synthetic_fixture': True}


if __name__ == '__main__':
    print(json.dumps([build(suffix) for suffix in SUFFIXES], indent=2))
