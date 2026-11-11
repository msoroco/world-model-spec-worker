"""Distinct source-shaped lateral trajectories for the three passing sweep controls.

Diagnostic fixtures only. They do not constitute physical Native realization.
"""
import copy
from hashlib import sha256
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
BASE = json.loads((HERE / 'lane-diagnostic-passing_boundary_crossing.json').read_text())
POINTS = {'passing_excursion-0000': .4,
          'passing_excursion-0001': .8,
          'passing_excursion-0002': .6}

def write(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n')

def sha(path):
    return sha256(path.read_bytes()).hexdigest()

def rows(value):
    return [json.loads(line) for line in value.splitlines() if line.strip()]

def encode(value):
    return ''.join(json.dumps(row) + '\n' for row in value)

def bind_pose(container, source, z):
    x = sum(point[0] for point in source['ego_corners_xy_m']) / 4
    y = sum(point[1] for point in source['ego_corners_xy_m']) / 4
    vertices = [[a, b, z] for a, b in source['ego_corners_xy_m'] for z in (0., 1.5)]
    if 'ego' in container:
        container['ego'].update(position_m=[x, y, z], body_vertices_m=vertices)
    observed = container.get('original_observations') or container.get('observed_evidence')
    if observed:
        for actor in observed.get('participants', []):
            if actor.get('actor_id') == source['ego_id']:
                actor.update(position_m=[x, y, z], body_vertices_m=vertices)

def build(suffix, fraction):
    data = copy.deepcopy(BASE)
    originals = rows(data['files']['marked_lane_sources.jsonl'])
    traces = rows(data['files']['trace.jsonl'])
    evidence = rows(data['files']['capture/evidence.jsonl'])
    if len(originals) != len(traces):
        raise ValueError('Diagnostic original trajectory is incomplete')
    by_frame = {}
    for i, (original, trace) in enumerate(zip(originals, traces)):
        lane = original['lane']
        polygon = lane['polygon_xy_m']
        heading = lane['lane_heading_xy']
        center = [sum(point[axis] for point in polygon) / len(polygon) for axis in (0, 1)]
        normal = (-heading[1], heading[0])
        target_offset = lane['lane_width_m'] * fraction * max(0., (i - 3) / (len(originals) - 4))
        old_center = [sum(point[axis] for point in original['ego_corners_xy_m']) / 4 for axis in (0, 1)]
        new_center = [center[axis] + normal[axis] * target_offset for axis in (0, 1)]
        delta = [new_center[axis] - old_center[axis] for axis in (0, 1)]
        original['ego_corners_xy_m'] = [[point[axis] + delta[axis] for axis in (0, 1)] for point in original['ego_corners_xy_m']]
        trace['position']['x'], trace['position']['y'] = new_center
        if 'position_m' in trace:
            trace['position_m'][:2] = new_center
        by_frame[original['frame']] = (original, trace['position_m'][2])
    for row in evidence:
        source = by_frame.get(row.get('original_frame'))
        if source:
            bind_pose(row, *source)
    for graph in data['graphs']:
        source = by_frame.get(graph['attributes'].get('frame'))
        if source:
            bind_pose(graph['attributes'], *source)
    data['files']['marked_lane_sources.jsonl'] = encode(originals)
    data['files']['trace.jsonl'] = encode(traces)
    data['files']['capture/evidence.jsonl'] = encode(evidence)
    capture = json.loads(data['files']['capture/manifest.json'])
    capture['sources']['trace.jsonl'] = sha256(data['files']['trace.jsonl'].encode()).hexdigest()
    data['files']['capture/manifest.json'] = json.dumps(capture, indent=2) + '\n'
    data['files']['lane_fixture_provenance.json'] = json.dumps({
        'diagnostic_fixture': True,
        'case_suffix': suffix,
        'requested_crossing_fraction': fraction,
        'note': 'Synthetic source-shaped distinct lateral target; no physical Native claim.'
    }) + '\n'
    path = HERE / ('lane-diagnostic-' + suffix + '.json')
    path.write_text(json.dumps(data, separators=(',', ':')) + '\n')
    if path.stat().st_size >= 2 * 1024 * 1024:
        raise ValueError('Diagnostic bundle exceeds local source size limit')
    recipe = {
        'format': 'worker-fixture-recipe',
        'sources': [{'path': 'diagnostic-input.json', 'source': str(path.relative_to(ROOT)), 'sha256': sha(path)}],
        'generator': {'source': str(path.relative_to(ROOT)), 'sha256': sha(path)},
    }
    recipe_path = HERE / ('lane-diagnostic-' + suffix + '-recipe.json')
    write(recipe_path, recipe)
    return str(recipe_path.relative_to(ROOT))

if __name__ == '__main__':
    recipes = {suffix: build(suffix, fraction) for suffix, fraction in POINTS.items()}
    for name in ('delivery-construction-manifest.json', 'execution-manifest.json'):
        path = HERE / name
        manifest = json.loads(path.read_text())
        for entry in manifest['cases']:
            suffix = entry['case_id'].rsplit('__', 1)[-1]
            if suffix in recipes:
                entry['fixture_recipe'] = recipes[suffix]
        write(path, manifest)
    print('Built', len(recipes), 'distinct synthetic passing trajectories')
