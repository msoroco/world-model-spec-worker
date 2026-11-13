"""Build unselected, executable roadside view-location variants."""
import hashlib
import json
import copy
from pathlib import Path

from build_through_speed_cases import replace_strings

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
OLD = 'yield_nearest_view_through_approaches'
PREFIX = ROOT.name + '__'

OCCLUDER = '''"""Temporary roadside obstruction for a view-location sweep."""
from contextlib import contextmanager
import math

BLUEPRINT = 'static.prop.streetbarrier'
X_M = -4.0

def projected_crossing_y(ego_x, ego_y, target_x=1.8, target_y=20.0):
    if not ego_x < X_M < target_x:
        raise ValueError('Sight segment does not cross obstruction station')
    return ego_y + (target_y - ego_y) * (X_M - ego_x) / (target_x - ego_x)

def projected_ego_x(center_y):
    fraction = (center_y - 1.8) / (20.0 - 1.8)
    if not 0.0 < fraction < 1.0:
        raise ValueError('Obstruction center lies outside authored sight fan')
    return (X_M - fraction * 1.8) / (1.0 - fraction)

@contextmanager
def view_occluder(world, center_y, *, location_factory=None, rotation_factory=None,
                  transform_factory=None):
    if not isinstance(center_y, (int, float)) or not math.isfinite(center_y):
        raise ValueError('Nonfinite roadside location')
    if location_factory is None:
        import carla
        location_factory, rotation_factory, transform_factory = carla.Location, carla.Rotation, carla.Transform
    blueprint = world.get_blueprint_library().find(BLUEPRINT)
    if blueprint is None:
        raise ValueError('Native roadside obstruction blueprint missing')
    pose = transform_factory(location_factory(x=X_M, y=float(center_y), z=0.0),
                             rotation_factory(yaw=0.0))
    actor = world.try_spawn_actor(blueprint, pose)
    if actor is None:
        raise ValueError('Native roadside obstruction could not spawn')
    try:
        actual = actor.get_transform().location
        if actor.type_id != BLUEPRINT or abs(actual.x-X_M) > .25 or abs(actual.y-center_y) > .25:
            raise ValueError('Native roadside obstruction differs from authored pose')
        vertices = list(actor.bounding_box.get_world_vertices(actor.get_transform()))
        if len(vertices) < 8 or not all(math.isfinite(float(getattr(v, axis)))
                                           for v in vertices for axis in ('x', 'y', 'z')):
            raise ValueError('Native roadside obstruction has invalid body geometry')
        limits = {axis: (min(float(getattr(v, axis)) for v in vertices),
                         max(float(getattr(v, axis)) for v in vertices))
                  for axis in ('x', 'y', 'z')}
        ego_x = projected_ego_x(center_y)
        fraction = (X_M - ego_x) / (1.8 - ego_x)
        ray_z = 1.75 - .25 * fraction
        if not (limits['x'][0] <= X_M <= limits['x'][1]
                and limits['y'][0] <= center_y <= limits['y'][1]
                and limits['z'][0] <= ray_z <= limits['z'][1]):
            raise ValueError('Native roadside obstruction cannot intersect authored eye ray')
        yield {'actor_id': actor.id, 'blueprint': BLUEPRINT,
               'native_location_m': [float(actual.x), float(actual.y), float(actual.z)],
               'body_bounds_m': {axis: list(pair) for axis, pair in limits.items()},
               'projected_eye_ray_height_m': ray_z,
               'projected_crossing_y_m': projected_crossing_y(-20., 1.8)}
    finally:
        actor.destroy()
'''

TEST = '''import unittest
from types import SimpleNamespace as NS
from view_location_world_setup import view_occluder, projected_crossing_y

class World:
    def __init__(self):
        self.actor = None
        self.blueprint = 'static.prop.streetbarrier'
        self.top_z = 2.0
    def get_blueprint_library(self):
        return NS(find=lambda name: self.blueprint if name == self.blueprint else None)
    def try_spawn_actor(self, blueprint, pose):
        self.actor = NS(type_id=blueprint, id=99, get_transform=lambda: pose,
                        bounding_box=NS(get_world_vertices=lambda transform:
                            [NS(x=transform.location.x+dx, y=transform.location.y+dy, z=z)
                             for dx in (-.5,.5) for dy in (-.5,.5) for z in (0., self.top_z)]),
                        destroy=lambda: setattr(self.actor, 'destroyed', True), destroyed=False)
        return self.actor

class ViewLocationTests(unittest.TestCase):
    def test_spawn_pose_cleanup_and_sight_geometry(self):
        world = World()
        with view_occluder(world, CENTER_Y, location_factory=lambda **kw: NS(**kw),
                           rotation_factory=lambda **kw: NS(**kw),
                           transform_factory=lambda location, rotation: NS(location=location, rotation=rotation)) as row:
            self.assertEqual(row['actor_id'], 99)
            self.assertEqual(row['native_location_m'][:2], [-4., CENTER_Y])
            self.assertAlmostEqual(row['projected_crossing_y_m'], projected_crossing_y(-20., 1.8))
            self.assertGreater(row['body_bounds_m']['z'][1], row['projected_eye_ray_height_m'])
            self.assertFalse(world.actor.destroyed)
        self.assertTrue(world.actor.destroyed)
    def test_short_body_rejected_and_destroyed(self):
        world = World(); world.top_z = 1.0
        with self.assertRaisesRegex(ValueError, 'cannot intersect authored eye ray'):
            with view_occluder(world, CENTER_Y, location_factory=lambda **kw: NS(**kw),
                               rotation_factory=lambda **kw: NS(**kw),
                               transform_factory=lambda location, rotation: NS(location=location, rotation=rotation)):
                pass
        self.assertTrue(world.actor.destroyed)
    def test_missing_blueprint_rejected(self):
        world = World(); world.blueprint = None
        with self.assertRaisesRegex(ValueError, 'blueprint missing'):
            with view_occluder(world, CENTER_Y, location_factory=lambda **kw: NS(**kw),
                               rotation_factory=lambda **kw: NS(**kw),
                               transform_factory=lambda location, rotation: NS(location=location, rotation=rotation)):
                pass
'''

def build():
    template = json.loads((ROOT / 'construction.json').read_text())
    cases = []
    for center_y in (12.0, 15.0, 18.0):
        label = int(center_y)
        suffix = f'yield_nearest_view_occluder_y{label}'
        draft = replace_strings(template, OLD, suffix)
        files = {item['path']: item for item in draft['files']}
        capture = files['yield_capture_sources.py']
        capture['content'] = capture['content'].replace('TARGET_XY = (1.8, 0.0)', 'TARGET_XY = (1.8, 20.0)')
        capture['content'] = capture['content'].replace('target_waypoint.road_id != 158195', 'target_waypoint.road_id != 158194')
        capture['content'] = capture['content'].replace('or target_waypoint.junction_id != JUNCTION', 'or target_waypoint.is_junction')
        capture['content'] = capture['content'].replace('through-highway junction lane', 'approaching through-highway lane')
        capture['content'] = capture['content'].replace("'target_road_id': 158195", "'target_road_id': 158194")
        capture['content'] = capture['content'].replace("'distance_to_intersection_m': float(distance),", "'distance_to_intersection_m': float(distance),\n           'ego_distance_to_junction_m': float(distance),")
        tests = files['tests/test_yield_capture_sources.py']
        tests['content'] = tests['content'].replace('if point.x < 0:', 'if point.x < 0:').replace('values = (158195, -1, 158191)', 'values = (158194, -1, 0)')
        tests['content'] = tests['content'].replace("dict(zip(('road_id', 'lane_id', 'junction_id'), values))", "dict(zip(('road_id', 'lane_id', 'junction_id'), values), is_junction=False)")
        tests['content'] = tests['content'].replace("self.assertEqual(ray['distance_to_intersection_m'], 12.)", "self.assertEqual(ray['distance_to_intersection_m'], 12.)\n        self.assertEqual(ray['ego_distance_to_junction_m'], 12.)")
        runner = files['runner.py']
        runner['content'] = runner['content'].replace('from yield_site import validate_authored_site', 'from yield_site import validate_authored_site\nfrom view_location_world_setup import view_occluder')
        runner['content'] = runner['content'].replace("with stage_case(world, config['selected_case_id']) as staging:", f"with stage_case(world, config['selected_case_id']) as staging, view_occluder(world, center_y={center_y:.1f}) as obstruction:")
        runner['content'] = runner['content'].replace("'native_map_id': world.get_map().name,", "'native_map_id': world.get_map().name,\n                'view_occluder': obstruction,")
        draft['files'].append({'path': 'view_location_world_setup.py', 'content': OCCLUDER})
        draft['files'].append({'path': 'tests/test_view_location_world_setup.py', 'content': TEST.replace('CENTER_Y', f'{center_y:.1f}')})
        path = ROOT / f'cases/view_location_y{label}/construction.json'
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(draft, indent=2) + '\n')
        cases.append({'case_id': PREFIX + suffix, 'construction': str(path.relative_to(ROOT)),
                      'construction_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                      'kind': 'diagnostic_unselected', 'occluder_center_y_m': center_y,
                      'target_xy_m': [1.8, 20.0]})
    # Invert the two-dimensional sight segment at the obstruction station.
    # These values locate candidate sample positions; the prop's actual mesh
    # and original camera review must establish any realized visibility edge.
    def projected_ego_distance(center_y):
        fraction = (center_y - 1.8) / (20.0 - 1.8)
        ego_x = (-4.0 - fraction * 1.8) / (1.0 - fraction)
        return -8.0 - ego_x

    manifest = {'format': 'worker-execution-manifest-draft', 'assignment_id': ROOT.name,
                'cases': cases, 'limitation': 'Native spawn, ray interception, original camera coverage and feasible view range require physical review.'}
    manifest['view_axis'] = {
        'world_setup_parameter': 'roadside_occluder_center_y_m',
        'target_xy_m': [1.8, 20.0], 'occluder_station_x_m': -4.0,
        'ego_lane_y_m': 1.8, 'junction_entry_x_m': -8.0,
        'sampled_center_y_m': [12.0, 15.0, 18.0],
        'projected_ego_distance_to_junction_m': [projected_ego_distance(y) for y in (12., 15., 18.)],
        'spacing_basis': 'Three authored center positions span near, middle and far candidate sight-line intersections within the 0–52 m approach sampling interval; mesh and cameras must validate feasibility.',
        'physical_limit': 'Projected intersections are geometry estimates, not realized occlusion or human recognition thresholds.'}
    (ROOT / 'view-location-draft-manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps({'draft_cases': len(cases)}))


def build_compatibility():
    """Make Native-shaped processing fixtures with source-bound prop context."""
    draft = json.loads((ROOT / 'view-location-draft-manifest.json').read_text())
    selected = json.loads((ROOT / 'execution-manifest.json').read_text())
    base_recipe = json.loads((ROOT / 'diagnostic-recipe.json').read_text())
    base_sources = {item['path']: item for item in base_recipe['sources']}
    common = ROOT / 'view-location-diagnostic-sources'
    common.mkdir(exist_ok=True)
    original_rays = [json.loads(line) for line in
                     (REPO / base_sources['visibility_rays.jsonl']['source']).read_text().splitlines()]
    rays = []
    for index, ray in enumerate(original_rays):
        row = copy.deepcopy(ray)
        ego_x = -20.0 + .1 * index
        row['observer_m'] = [ego_x, 1.8, 1.75]
        row['target_m'] = [1.8, 20.0, 1.5]
        row['target_road_id'] = 158194
        row['target_lane_id'] = -1
        row['ego_distance_to_junction_m'] = row['distance_to_intersection_m']
        if row['blockers']:
            fraction = (-4.0 - ego_x) / (1.8 - ego_x)
            row['blockers'] = [{'label': 'synthetic_diagnostic_wall',
                                'location_m': [-4.0, 1.8 + fraction * 18.2,
                                               1.75 - fraction * .25]}]
        rays.append(row)
    (common / 'visibility_rays.jsonl').write_text(''.join(json.dumps(row) + '\n' for row in rays))
    samples = json.loads((REPO / base_sources['visibility_samples.json']['source']).read_text())
    for sample in samples:
        sample['ego_distance_to_junction_m'] = sample['distance_to_intersection_m']
    (common / 'visibility_samples.json').write_text(json.dumps(samples, indent=2) + '\n')
    template = selected['cases'][0]
    compat = {key: selected[key] for key in ('format', 'assignment_id', 'runtime_manifest_sha256')}
    compat['cases'] = []
    for case in draft['cases']:
        center = int(case['occluder_center_y_m'])
        directory = ROOT / f'cases/view_location_y{center}/diagnostic-sources'
        (directory / 'capture').mkdir(parents=True, exist_ok=True)
        context = json.loads((REPO / base_sources['road_context.json']['source']).read_text())
        context['view_occluder'] = {'actor_id': 900 + center, 'blueprint': 'static.prop.streetbarrier',
                                    'native_location_m': [-4.0, float(center), 0.0],
                                    'source_kind': 'synthetic_diagnostic'}
        (directory / 'road_context.json').write_text(json.dumps(context, indent=2) + '\n')
        cap = json.loads((REPO / base_sources['capture/manifest.json']['source']).read_text())
        cap['case_id'] = case['case_id']
        cap['view_occluder_source'] = 'road_context.json'
        (directory / 'capture/manifest.json').write_text(json.dumps(cap, indent=2) + '\n')
        overrides = {
            'visibility_rays.jsonl': common / 'visibility_rays.jsonl',
            'visibility_samples.json': common / 'visibility_samples.json',
            'road_context.json': directory / 'road_context.json',
            'capture/manifest.json': directory / 'capture/manifest.json'}
        recipe = copy.deepcopy(base_recipe)
        for item in recipe['sources']:
            if item['path'] in overrides:
                source = overrides[item['path']]
                item['source'] = str(source.relative_to(REPO))
                item['sha256'] = hashlib.sha256(source.read_bytes()).hexdigest()
        recipe_path = ROOT / f'cases/view_location_y{center}/diagnostic-recipe.json'
        recipe_path.write_text(json.dumps(recipe, indent=2) + '\n')
        entry = copy.deepcopy(template)
        for key in ('candidates', 'negative', 'offline', 'compatibility',
                    'delivery_acceptance', 'physical_preparation'):
            entry.pop(key, None)
        entry.update(case_id=case['case_id'], kind='diagnostic_unselected',
                     construction=case['construction'],
                     construction_sha256=case['construction_sha256'],
                     fixture_recipe=str(recipe_path.relative_to(REPO)),
                     candidate_risk={'status': 'physical', 'reason':
                                     'Prop mesh, realized ray occlusion and original pixels unverified'},
                     occluder_center_y_m=case['occluder_center_y_m'])
        compat['cases'].append(entry)
    (ROOT / 'view-location-compatibility-manifest.json').write_text(
        json.dumps(compat, indent=2) + '\n')
    print(json.dumps({'compatibility_cases': len(compat['cases']),
                      'source_kind': 'synthetic_diagnostic'}))


def bind_semantics():
    draft = json.loads((ROOT / 'view-location-draft-manifest.json').read_text())
    plan_path = ROOT / 'case-plan.json'
    plan = json.loads(plan_path.read_text())
    proposals_path = ROOT / 'proposals/cases.json'
    proposals = json.loads(proposals_path.read_text())
    plan_template = next(row for row in plan['cases'] if 'sign_angle_zero' in row['case_id'])
    proposal_template = next(row for row in proposals['cases'] if 'sign_angle_zero' in row['case_id'])
    for case in draft['cases']:
        case_id = case['case_id']
        center = case['occluder_center_y_m']
        if not any(row['case_id'] == case_id for row in plan['cases']):
            row = copy.deepcopy(plan_template)
            row.update(case_id=case_id,
                       purpose=f'Authored roadside occluder center y={center:.1f} m with original ray and camera review; no legal view threshold')
            plan['cases'].append(row)
        for disposition in plan['requirement_dispositions']:
            if disposition['status'] == 'selected_required' and case_id not in disposition.get('case_ids', []):
                disposition['case_ids'].append(case_id)
        if not any(row['case_id'] == case_id for row in proposals['cases']):
            row = copy.deepcopy(proposal_template)
            row.update(case_id=case_id,
                       rationale=f'Roadside occluder center y={center:.1f} m is an authored world setup input; original sight rays and cameras must verify realized view.',
                       paired_probe_id='c158190-view-location-y12-y15-y18',
                       deliberate_differences=['view_occluder_center_y_m'],
                       probe={'primary_variable': 'view_occluder_center_y_m',
                              'comparison_or_standard': 'three-point authored geometry contrast; no legal recognition threshold',
                              'target_value_or_branch': center})
            variables = row['variable_assignments']
            variables.pop('authored_sign_hOffset_rad', None)
            variables.pop('native_sign_rotation_deg', None)
            variables['view_occluder_center_y_m'] = {'kind': 'world_setup', 'value': center, 'unit': 'm'}
            variables['through_lane_ray_target_xy_m'] = {'kind': 'world_setup', 'value': [1.8, 20.0], 'unit': 'm'}
            for channel in row['recording_description']['channels']:
                if channel['name'] == 'through_highway_sight_clear':
                    channel['method'] = 'original collision ray to approaching through-highway lane point, joined to source cameras'
            proposals['cases'].append(row)
    plan_path.write_text(json.dumps(plan, indent=2) + '\n')
    proposals_path.write_text(json.dumps(proposals, indent=2) + '\n')
    print(json.dumps({'semantic_view_cases': len(draft['cases'])}))

if __name__ == '__main__':
    build()
    bind_semantics()
    build_compatibility()
