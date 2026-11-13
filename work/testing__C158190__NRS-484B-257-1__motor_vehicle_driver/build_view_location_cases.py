"""Build unselected, executable roadside view-location variants."""
import hashlib
import json
from pathlib import Path

from build_through_speed_cases import replace_strings

ROOT = Path(__file__).resolve().parent
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
        yield {'actor_id': actor.id, 'blueprint': BLUEPRINT,
               'native_location_m': [float(actual.x), float(actual.y), float(actual.z)],
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
    def get_blueprint_library(self):
        return NS(find=lambda name: self.blueprint if name == self.blueprint else None)
    def try_spawn_actor(self, blueprint, pose):
        self.actor = NS(type_id=blueprint, id=99, get_transform=lambda: pose,
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
            self.assertFalse(world.actor.destroyed)
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
    manifest = {'format': 'worker-execution-manifest-draft', 'assignment_id': ROOT.name,
                'cases': cases, 'limitation': 'Native spawn, ray interception, original camera coverage and feasible view range require physical review.'}
    (ROOT / 'view-location-draft-manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps({'draft_cases': len(cases)}))

if __name__ == '__main__':
    build()
