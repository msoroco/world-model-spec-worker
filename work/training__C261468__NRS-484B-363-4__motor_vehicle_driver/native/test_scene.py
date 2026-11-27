"""CPU creation/geometry tests for the surveyed school-zone pass pair."""

import copy
import importlib.util
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('c261468_scene', HERE / 'scene.py')
scene = importlib.util.module_from_spec(spec)
spec.loader.exec_module(scene)


class Location:
    def __init__(self, x, y, z):
        self.x, self.y, self.z = x, y, z

    def distance(self, other):
        return ((self.x - other.x) ** 2 + (self.y - other.y) ** 2 +
                (self.z - other.z) ** 2) ** .5


class Rotation:
    def __init__(self, yaw):
        self.yaw = yaw


class Transform:
    def __init__(self, location, rotation):
        self.location, self.rotation = location, rotation


class Carla:
    Location, Rotation, Transform = Location, Rotation, Transform


class Actor:
    def __init__(self, kind, location):
        self.type_id, self.location, self.destroyed = kind, location, False

    def get_location(self):
        return self.location

    def destroy(self):
        self.destroyed = True


class Actors:
    def __init__(self, devices):
        self.devices = devices

    def find(self, actor_id):
        return self.devices.get(actor_id)


class Blueprints:
    def find(self, blueprint):
        if not blueprint.startswith('vehicle.'):
            raise ValueError('Unexpected vehicle blueprint')
        return blueprint


class Map:
    name = 'reviewed_map'


class World:
    def __init__(self, survey):
        devices = [survey['installed_sign']] + survey['beacon']['yellow_lights']
        self.devices = {row['actor_id']: Actor(row['asset_id'], Location(*row['xyz_m']))
                        for row in devices}
        self.spawned = []
        self.fail_second = False

    def get_map(self):
        return Map()

    def get_actors(self):
        return Actors(self.devices)

    def get_blueprint_library(self):
        return Blueprints()

    def try_spawn_actor(self, blueprint, transform):
        if self.fail_second and self.spawned:
            return None
        actor = Actor(blueprint, transform.location)
        self.spawned.append((actor, transform))
        return actor


def fixture():
    aid = scene.ASSIGNMENT
    source = {'path': 'reviewed/source.json', 'sha256': 'a' * 64}
    survey = {
        'assignment_id': aid, 'case_id': aid + '__school_in_session_active',
        'map_name': 'reviewed_map', 'road_id': 8, 'road_axis_xy': [1, 0],
        'zone_station_bounds_m': [0, 100], 'zone_kind': 'school_zone',
        'ego': {'blueprint': 'vehicle.tesla.model3', 'xyz_m': [10, 0, 0.1], 'yaw_deg': 0},
        'other': {'blueprint': 'vehicle.audi.a2', 'xyz_m': [30, 0, 0.1], 'yaw_deg': 0},
        'installed_sign': {'actor_id': 30, 'asset_id': 'static.prop.school_sign',
                           'xyz_m': [5, 4, 0], 'zone_kind': 'school_zone'},
        'beacon': {'sign_actor_id': 30, 'yellow_lights': [
            {'actor_id': 31, 'asset_id': 'static.prop.yellow_lamp', 'color': 'yellow', 'xyz_m': [5, 4, 2]},
            {'actor_id': 32, 'asset_id': 'static.prop.yellow_lamp', 'color': 'yellow', 'xyz_m': [5, 4, 3]}]},
    }
    for name in ('calendar', 'operation_hours', 'civil_time', 'zone_designation',
                 'zone_boundary', 'installed_sign', 'pass_route', 'beacon_controller'):
        survey[name + '_source'] = dict(source)
    cases = {row['case_id']: row for row in json.loads(scene.CASE_PLAN.read_text())['cases']}
    survey['planned_context'] = cases[survey['case_id']]['requested_context']
    return survey


def rejects(value, fragment):
    try:
        scene.validate_survey(value)
    except ValueError as exc:
        assert fragment in str(exc), (fragment, str(exc))
    else:
        raise AssertionError('Invalid original survey accepted: ' + fragment)


def main():
    source = fixture()
    assert scene.validate_survey(source) == source['case_id']
    world = World(source)
    ego, other = scene.spawn_pass_pair(world, Carla, source)
    assert (ego.type_id, other.type_id) == ('vehicle.tesla.model3', 'vehicle.audi.a2')
    assert [row[1].location.x for row in world.spawned] == [10, 30]
    changed = copy.deepcopy(source)
    changed['other']['yaw_deg'] = 180
    rejects(changed, 'share the route direction')
    changed = copy.deepcopy(source)
    changed['ego']['yaw_deg'] = changed['other']['yaw_deg'] = 180
    rejects(changed, 'against route axis')
    changed = copy.deepcopy(source)
    changed['ego']['xyz_m'][0] = 35
    rejects(changed, 'start behind')
    changed = copy.deepcopy(source)
    changed['zone_designation_source'] = None
    rejects(changed, 'zone_designation_source')
    changed = copy.deepcopy(source)
    changed['beacon']['yellow_lights'][1]['actor_id'] = 31
    rejects(changed, 'must be distinct')
    changed = copy.deepcopy(source)
    changed['zone_kind'] = 'school_crossing_zone'
    rejects(changed, 'Installed zone kind differs')
    changed = copy.deepcopy(source)
    changed['planned_context']['beacon_yellow_alternating'] = False
    rejects(changed, 'Reviewed condition differs')
    world = World(source)
    world.devices[31].type_id = 'wrong-lamp'
    try:
        scene.spawn_pass_pair(world, Carla, source)
    except ValueError as exc:
        assert 'differs from survey' in str(exc)
    else:
        raise AssertionError('Wrong live sign/lamp actor accepted')
    world = World(source)
    world.fail_second = True
    try:
        scene.spawn_pass_pair(world, Carla, source)
    except ValueError as exc:
        assert 'spawn failed: other' in str(exc)
    else:
        raise AssertionError('Missing overtaken actor accepted')
    assert world.spawned[0][0].destroyed
    print(json.dumps({'passed': True, 'constructed_vehicles': 2,
                      'rejected_source_or_geometry_variants': 9,
                      'partial_spawn_cleanup_passed': True,
                      'native_executed': False, 'physical_acceptance_claimed': False}))


if __name__ == '__main__':
    main()
