import copy
import json
import unittest
from pathlib import Path
from runner import FRAMES, RATE, check, phase_at
from body_geometry import choose_curbside_spawn, scene_clearance, spawn_sidewalk_pedestrian

class Vec:
    def __init__(self, x, y, z=0):
        self.x, self.y, self.z = x, y, z

class Box:
    def __init__(self):
        self.location, self.extent = Vec(0, 0), Vec(1, 0.5)

class Pose:
    def __init__(self, x, y, yaw=0):
        self.x, self.y, self.yaw = x, y, yaw
    def transform(self, point):
        import math
        angle = math.radians(self.yaw)
        return Vec(self.x + point.x * math.cos(angle) - point.y * math.sin(angle),
                   self.y + point.x * math.sin(angle) + point.y * math.cos(angle))

class Actor:
    def __init__(self, actor_id, x, y, yaw=0, kind='vehicle.test'):
        self.id, self.type_id = actor_id, kind
        self.bounding_box = Box()
        self.pose = Pose(x, y, yaw)
    def get_transform(self):
        return self.pose
    def get_velocity(self):
        return Vec(0, 0)

class Lane:
    def __init__(self, lane_type, right=None):
        self.lane_type, self.right = lane_type, right
        self.road_id, self.section_id, self.lane_id = 1, 0, -1
    def get_right_lane(self):
        return self.right

class Map:
    def __init__(self, lanes):
        self.lanes = lanes
    def get_waypoint(self, location, *, project_to_road, lane_type):
        assert project_to_road is False
        assert lane_type == 'Driving'
        return self.lanes[location]

class Spawn:
    def __init__(self, location):
        self.location = location

class Blueprint:
    id = 'walker.pedestrian.0001'

class Library:
    def filter(self, selector):
        assert selector == 'walker.pedestrian.*'
        return [Blueprint()]

class World:
    def __init__(self):
        self.created = None
    def get_blueprint_library(self):
        return Library()
    def try_spawn_actor(self, blueprint, pose):
        self.created = (blueprint.id, pose.location.z)
        return Actor(9, 2, 2, kind='walker.pedestrian.0001')

class ExactCaptureContract(unittest.TestCase):
    def setUp(self):
        self.config = json.loads(Path('config.json').read_text())

    def test_window_and_cameras(self):
        result = check(self.config)
        self.assertEqual((result['frames'], result['rate_hz']), (600, 20))
        self.assertEqual(len(result['camera_views']), 4)
        self.assertEqual(len([phase_at(self.config, i) for i in range(FRAMES)]), 600)
        self.assertIsNone(result['legal_verdict'])

    def test_reject_missing_camera(self):
        bad = copy.deepcopy(self.config)
        bad['cameras'].pop()
        with self.assertRaisesRegex(ValueError, 'Four named'):
            check(bad)

    def test_reject_short_or_discontinuous_schedule(self):
        bad = copy.deepcopy(self.config)
        bad['control_phases'][-1]['last_frame'] = 598
        with self.assertRaises(ValueError):
            check(bad)
        bad = copy.deepcopy(self.config)
        bad['control_phases'][1]['first_frame'] += 1
        with self.assertRaises(ValueError):
            check(bad)

    def test_reject_invented_legal_verdict(self):
        bad = copy.deepcopy(self.config)
        bad['legal_verdict'] = 'careless'
        with self.assertRaises(ValueError):
            check(bad)

    def test_endpoint_rejection(self):
        with self.assertRaises(ValueError):
            phase_at(self.config, FRAMES)

    def test_original_body_clearance_both_directions(self):
        ego = Actor(1, 0, 0)
        ahead = Actor(2, 4, 0)
        behind = Actor(3, -4, 0)
        for other in (ahead, behind):
            result = scene_clearance(ego, [ego, other])
            self.assertAlmostEqual(result['minimum_surface_gap_m'], 2)
            self.assertEqual(len(result['participants']), 1)
        overlapping = scene_clearance(ego, [Actor(4, 0.5, 0.1, 30)])
        self.assertEqual(overlapping['minimum_surface_gap_m'], 0)

    def test_unknown_gap_without_source_participant(self):
        ego = Actor(1, 0, 0)
        sensor = Actor(7, 0, 0, kind='sensor.camera.rgb')
        result = scene_clearance(ego, [ego, sensor])
        self.assertIsNone(result['minimum_surface_gap_m'])
        self.assertEqual(result['participants'], [])

    def test_selects_source_observed_curbside_lane(self):
        spawns = [Spawn(0), Spawn(1)]
        native_map = Map([Lane('Driving'), Lane('Driving', Lane('Sidewalk'))])
        selected, info = choose_curbside_spawn(native_map, spawns, 0,
                                               'Driving', ('Sidewalk', 'Shoulder', 'Parking'))
        self.assertEqual(selected, 1)
        self.assertEqual(info['right_neighbor_type'], 'Sidewalk')
        with self.assertRaisesRegex(ValueError, 'No source-observed curbside'):
            choose_curbside_spawn(Map([Lane('Driving'), Lane('Driving')]),
                                  spawns, 0, 'Driving', ('Sidewalk',))

    def test_creates_sidewalk_pedestrian_from_native_lane(self):
        world = World()
        lane = Lane('Sidewalk')
        lane.transform = type('Transform', (), {'location': Vec(2, 2, 0)})()
        walker = spawn_sidewalk_pedestrian(world, lane, 'walker.pedestrian.*')
        self.assertEqual(walker.type_id, 'walker.pedestrian.0001')
        self.assertEqual(world.created, ('walker.pedestrian.0001', 0.3))
        with self.assertRaisesRegex(ValueError, 'Exact adjacent-sidewalk'):
            spawn_sidewalk_pedestrian(world, lane, 'vehicle.*')
