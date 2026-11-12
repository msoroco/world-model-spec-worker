import math
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from center_turn_construction import control_step, route_targets, select_candidate
from turn_origin_capture import TurnOriginRecorder
from turn_origin_measurement import measure


class Node:
    def __init__(self, x, y, heading, lane, *, road=17, junction=False, marked=True):
        self.transform = type('T', (), {})()
        self.transform.location = type('L', (), {'x': x, 'y': y})()
        self.transform.get_forward_vector = lambda: type('V', (), {
            'x': math.cos(heading), 'y': math.sin(heading)})()
        self.road_id, self.lane_id, self.is_junction = road, lane, junction
        self.lane_type = 'Driving'
        mark = type('M', (), {'type': 'Solid'})() if marked else None
        self.left_lane_marking = self.right_lane_marking = mark
        self.successor = []
        self.right = None

    def next(self, distance):
        return self.successor

    def get_right_lane(self):
        return self.right


class FakeMap:
    def __init__(self, start):
        self.start = start

    def generate_waypoints(self, spacing):
        return [self.start]


def scene(direction=1, *, marked=True, outer_turn=True):
    heading = 0 if direction == 1 else math.pi
    turn = -math.pi/2 if direction == 1 else math.pi/2
    center = [Node(direction*i*2, 0, heading, direction, marked=marked)
              for i in range(5)]
    outer = [Node(direction*i*2, 3, heading, 2*direction, marked=marked)
             for i in range(5)]
    for chain in (center, outer):
        for a, b in zip(chain, chain[1:]):
            a.successor = [b]
    for a, b in zip(center, outer):
        a.right = b
    center_junction = Node(direction*10, 0, heading, direction, junction=True)
    outer_junction = Node(direction*10, 3, heading, 2*direction, junction=True)
    center_exit = Node(direction*10, -direction*8, turn, direction, road=25)
    outer_exit = Node(direction*10, -direction*8, turn, direction,
                      road=25 if outer_turn else 26)
    center[-1].successor = [center_junction]
    outer[-1].successor = [outer_junction]
    center_junction.successor = [center_exit]
    outer_junction.successor = [outer_exit]
    return FakeMap(center[0])


class CenterTurnConstructionTests(unittest.TestCase):
    def test_both_directions_have_distinct_origins_and_connected_left_exits(self):
        for direction, label in ((1, 'east'), (-1, 'west')):
            with self.subTest(direction=label):
                selected = select_candidate(scene(direction), approach_steps=4,
                                            direction=label)
                self.assertEqual(selected['center_lane_id'], direction)
                self.assertEqual(selected['outer_lane_id'], 2*direction)
                self.assertLess(selected['requested_turn_deg'], -45)
                self.assertLess(selected['outer_requested_turn_deg'], -45)
                self.assertFalse(selected['designation_authority_verified'])
                center = route_targets(selected, origin='center')
                outer = route_targets(selected, origin='outer')
                self.assertEqual(len(center), 7)
                self.assertNotEqual(center[0], outer[0])
                self.assertEqual(center[-1], outer[-1])

    def test_unmarked_and_unconnected_outer_target_rejected(self):
        for fake in (scene(marked=False), scene(outer_turn=False)):
            with self.assertRaisesRegex(ValueError, 'No connected marked'):
                select_candidate(fake, approach_steps=4)

    def test_wrong_direction_and_bad_sampling_rejected(self):
        with self.assertRaisesRegex(ValueError, 'No connected marked'):
            select_candidate(scene(), approach_steps=4, direction='west')
        with self.assertRaisesRegex(ValueError, 'Invalid center-turn'):
            select_candidate(scene(), approach_steps=3)

    def test_feedback_tracks_left_target_and_checks_native_state(self):
        command = control_step((0, 0), (1, 0), (0, 0), (3, -2))
        self.assertLess(command['steer'], 0)
        self.assertGreater(command['throttle'], 0)
        with self.assertRaisesRegex(ValueError, 'Invalid Native'):
            control_step((0, 0), (1, 0), (0, 0), (0, 0))
        with self.assertRaisesRegex(ValueError, 'target speed'):
            control_step((0, 0), (1, 0), (0, 0), (3, -2), target_speed_mps=20)

    def test_capture_retains_map_marking_refs_and_native_origin(self):
        selected = select_candidate(scene(), approach_steps=4)
        class Map:
            def __init__(self): self.rows = [*selected['center_approach'][:2],
                                             selected['junction'], selected['junction'],
                                             selected['exit']]
            def get_waypoint(self, location, **kwargs): return self.rows.pop(0)
        class Ego:
            id = 31
            def __init__(self): self.heading = 0
            def get_location(self): return None
            def get_transform(self):
                heading = self.heading
                return type('T', (), {'get_forward_vector': lambda self: type('V', (), {
                    'x': math.cos(heading), 'y': math.sin(heading)})()})()
        with tempfile.TemporaryDirectory() as tmp:
            ego = Ego()
            recorder = TurnOriginRecorder(tmp, Map(), selected)
            for i, heading in enumerate((0, 0, -.35, -1., -math.pi/2)):
                ego.heading = heading
                recorder.append(ego, 100+i, i*.05)
            recorder.close()
            result = measure(Path(tmp) / 'turn_origin_native.jsonl')
            self.assertTrue(result['origin_matches_center_lane'])
            self.assertEqual(result['first_observed_left_frame'], 104)
            self.assertTrue(all(x.startswith('road:17:lane:1:') for x in
                                result['center_marking_source_ids']))
            self.assertFalse(result['designation_authority_verified'])


if __name__ == '__main__':
    unittest.main()
