import math
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from u_turn_construction import (participant_placement, select_u_turn_scene,
                                 u_turn_targets, control_step,
                                 select_no_u_turn_device,
                                 verify_incoming_sight_extent)
from runner import CAMERAS, PREFIX, check_config


class Waypoint:
    def __init__(self, x, y, yaw, lane, *, road=7, junction=False):
        self.road_id, self.lane_id, self.is_junction = road, lane, junction
        self.lane_type = 'Driving'
        radians = math.radians(yaw)
        self.transform = SimpleNamespace(
            location=SimpleNamespace(x=x, y=y),
            get_forward_vector=lambda: SimpleNamespace(
                x=math.cos(radians), y=math.sin(radians)))
        self.left = self.right = None

    def get_left_lane(self):
        return self.left

    def get_right_lane(self):
        return self.right


class Map:
    def __init__(self, starts, landmarks=()):
        self.starts = starts
        self.landmarks = landmarks

    def generate_waypoints(self, spacing):
        assert spacing == 2.0
        return self.starts

    def get_all_landmarks(self):
        return self.landmarks


class ConstructionTests(unittest.TestCase):
    def scene(self, opposite_yaw=180, junction=False):
        approach = Waypoint(0, 0, 0, -1, junction=junction)
        opposite = Waypoint(0, 3.5, opposite_yaw, 1)
        approach.left = opposite
        return Map([approach])

    def test_opposing_geometry_and_distinct_participant_roles(self):
        scene = select_u_turn_scene(self.scene())
        self.assertEqual((scene['approach_lane_id'], scene['opposite_lane_id']),
                         (-1, 1))
        route = u_turn_targets(scene)
        self.assertEqual(len(route['targets_xy_m']), 25)
        self.assertEqual(route['targets_xy_m'][0], [0, 0])
        self.assertAlmostEqual(route['targets_xy_m'][-1][1], 3.5)
        self.assertGreater(max(x for x, _ in route['targets_xy_m']), 4)
        locations = participant_placement(scene)
        self.assertGreater(locations['oncoming'][0], 0)
        self.assertLess(locations['following'][0], 0)
        self.assertNotEqual(locations['oncoming'], locations['following'])

    def test_rejects_same_direction_and_junction(self):
        for mapping in (self.scene(opposite_yaw=0), self.scene(junction=True)):
            with self.assertRaisesRegex(ValueError, 'No requested Native'):
                select_u_turn_scene(mapping)

    def test_candidate_knobs(self):
        scene = select_u_turn_scene(self.scene())
        self.assertNotEqual(u_turn_targets(scene, arc_extension_m=4)['targets_xy_m'],
                            u_turn_targets(scene, arc_extension_m=6)['targets_xy_m'])
        self.assertNotEqual(participant_placement(scene, oncoming_distance_m=12),
                            participant_placement(scene, oncoming_distance_m=24))

    def test_controller_steers_toward_u_turn_arc(self):
        straight = control_step((0, 0), (1, 0), (0, 0), (5, 0))
        turning = control_step((0, 0), (1, 0), (0, 0), (5, 3))
        self.assertEqual(straight['steer'], 0)
        self.assertGreater(turning['steer'], 0)
        self.assertGreater(turning['throttle'], 0)
        with self.assertRaisesRegex(ValueError, 'invalid'):
            control_step((0, 0), (0, 0), (0, 0), (5, 3))

    def test_runner_rejects_comparison_drift_without_carla(self):
        cameras = [{'name': name, 'width': item[2][0], 'height': item[2][1],
                    'fov_deg': item[3]} for name, item in CAMERAS.items()]
        base = {'selected_case_id': PREFIX+'safety_clear',
                'law_id': 'NRS-484B-403-1', 'cell_id': 'C230627',
                'actor': 'motor_vehicle_driver', 'rate_hz': 20,
                'frames': 160, 'duration_s': 8, 'cameras': cameras,
                'case': {'case_id': PREFIX+'safety_clear',
                         'recording_description': {'channels': []}},
                'engineering': {'oncoming_distance_m': 24}}
        self.assertEqual(check_config(base), PREFIX+'safety_clear')
        drift = dict(base, engineering={'oncoming_distance_m': 12})
        with self.assertRaisesRegex(ValueError, 'Clear comparison'):
            check_config(drift)
        conflict = dict(base, selected_case_id=PREFIX+'safety_conflict',
                        case={'case_id': PREFIX+'safety_conflict',
                              'recording_description': {'channels': []}},
                        engineering={'oncoming_distance_m': 12})
        self.assertEqual(check_config(conflict), PREFIX+'safety_conflict')
        for candidate in ({'waypoint_spacing_m': 1},
                          {'arc_extension_m': 4},
                          {'following_distance_m': 24}):
            self.assertEqual(check_config(dict(base, engineering={
                'oncoming_distance_m': 24, **candidate})), PREFIX+'safety_clear')

    def test_mapped_no_u_turn_device_source_and_negative_controls(self):
        scene_map = self.scene()
        scene = select_u_turn_scene(scene_map)
        device = SimpleNamespace(id='sign-1', road_id=7, name='NO_U_TURN',
                                 type='regulatory', value='',
                                 transform=SimpleNamespace(
                                     location=SimpleNamespace(x=12, y=2)))
        scene_map.landmarks = [device]
        found = select_no_u_turn_device(scene_map, scene)
        self.assertEqual(found['landmark_id'], 'sign-1')
        self.assertIsNone(found['official_device_status'])
        self.assertIsNone(found['pixel_visibility_status'])
        scene_map.landmarks = [SimpleNamespace(**{**vars(device), 'road_id': 8})]
        with self.assertRaisesRegex(ValueError, 'No source-mapped'):
            select_no_u_turn_device(scene_map, scene)
        scene_map.landmarks = [SimpleNamespace(**{**vars(device), 'name': 'speed_limit'})]
        with self.assertRaisesRegex(ValueError, 'No source-mapped'):
            select_no_u_turn_device(scene_map, scene)

    def test_incoming_sight_extent_both_lanes_all_targets(self):
        scene = select_u_turn_scene(self.scene())
        route = u_turn_targets(scene)
        class SightMap:
            short_lane = None
            def get_waypoint_xodr(self, road, lane, station):
                self.count += 1
                return SimpleNamespace(lane_type='Driving',
                    previous=lambda distance: [] if lane == self.short_lane else
                    [SimpleNamespace(lane_type='Driving')])
        mapping = SightMap()
        mapping.count = 0
        project = lambda x,y: SimpleNamespace(road_id=7, s=100.0)
        result = verify_incoming_sight_extent(mapping, scene, route, project)
        self.assertEqual(mapping.count, 2*len(route['targets_xy_m']))
        self.assertFalse(result['sight_horizon_measured'])
        mapping.short_lane = scene['opposite_lane_id']
        with self.assertRaisesRegex(ValueError, 'shorter or ambiguous'):
            verify_incoming_sight_extent(mapping, scene, route, project)
        with self.assertRaisesRegex(ValueError, 'projection missing'):
            verify_incoming_sight_extent(mapping, scene, route, lambda x,y: None)


if __name__ == '__main__':
    unittest.main()
