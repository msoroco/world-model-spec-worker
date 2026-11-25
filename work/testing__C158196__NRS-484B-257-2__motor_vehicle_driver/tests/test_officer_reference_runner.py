import importlib.util
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace as NS


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
SPEC = importlib.util.spec_from_file_location('c158196_officer_reference_runner',
                                              ROOT / 'officer_reference_runner.py')
RUNNER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(RUNNER)
from officer_performer import spawn as spawn_officer
PREFIX = 'testing__C158196__NRS-484B-257-2__motor_vehicle_driver__'


class Blueprint:
    def __init__(self, name):
        self.name, self.attributes = name, {}

    def set_attribute(self, key, value):
        self.attributes[key] = value


class World:
    def __init__(self):
        self.blueprints = []

    def get_blueprint_library(self):
        def find(name):
            blueprint = Blueprint(name)
            self.blueprints.append(blueprint)
            return blueprint
        return NS(find=find)

    def try_spawn_actor(self, blueprint, transform):
        return NS(id=8, blueprint=blueprint, transform=transform)


class OfficerReferenceRunnerTests(unittest.TestCase):
    def setUp(self):
        self.carla = NS(Location=lambda **kw: NS(**kw),
                        Rotation=lambda **kw: NS(**kw),
                        Transform=lambda location, rotation:
                        NS(location=location, rotation=rotation))

    def test_exact_six_cases_and_authored_reference_kinds(self):
        expected = [('officer_controls_go', 'stop_line'),
                    ('officer_controls_hold', 'stop_line'),
                    ('officer_present_inactive', 'stop_line'),
                    ('stop_line_reference', 'stop_line'),
                    ('crosswalk_reference', 'near_crosswalk'),
                    ('nearest_view_reference', 'nearest_view')]
        for suffix, kind in expected:
            selected = RUNNER.validate_config(PREFIX + suffix)
            self.assertEqual(selected['reference']['kind'], kind)
            self.assertEqual(selected['row']['rate_hz'], 20)
        with self.assertRaisesRegex(ValueError, 'Unselected exact'):
            RUNNER.validate_config(PREFIX + 'unselected')

    def test_native_spawn_and_four_camera_construction(self):
        world = World()
        config = RUNNER.validate_config(PREFIX + 'officer_controls_go')['camera_config']
        actor = RUNNER._spawn_vehicle(world, world.get_blueprint_library(),
                                      'vehicle.tesla.model3', [-40.0, 1.8],
                                      0.0, 'ego', self.carla)
        self.assertEqual(actor.transform.location.x, -40.0)
        self.assertEqual(actor.blueprint.attributes['role_name'], 'c158196_257_2_ego')
        blueprints, mounts = RUNNER._camera_construction(world, config, self.carla)
        self.assertEqual(set(blueprints), set(RUNNER.CAMERAS))
        self.assertEqual(blueprints['overview'].attributes['image_size_x'], '1920')
        self.assertEqual(mounts['approach']['attach_to'], 'ego')

    def test_officer_performer_location_and_cleanup(self):
        class PerformerWorld:
            def try_spawn_actor(self, blueprint, transform):
                actor = NS(id=3, destroyed=False,
                           get_location=lambda: transform.location)
                actor.destroy = lambda: setattr(actor, 'destroyed', True)
                self.actor = actor
                return actor

        world = PerformerWorld()
        transform = RUNNER._transform(
            self.carla, {'x': -3.0, 'y': -5.5, 'z': 0.5},
            {'yaw': -90.0, 'pitch': 0.0, 'roll': 0.0})
        with spawn_officer(world, Blueprint('walker.pedestrian.0001'),
                           transform, self.carla.Location(x=0, y=0, z=0)) as actor:
            self.assertEqual(actor.id, 3)
        self.assertTrue(world.actor.destroyed)
        outside = RUNNER._transform(
            self.carla, {'x': -40.0, 'y': 0.0, 'z': 0.5},
            {'yaw': 0.0, 'pitch': 0.0, 'roll': 0.0})
        with self.assertRaisesRegex(ValueError, 'outside authored junction band'):
            with spawn_officer(world, Blueprint('walker.pedestrian.0001'),
                               outside, self.carla.Location(x=0, y=0, z=0)):
                pass


if __name__ == '__main__':
    unittest.main()
