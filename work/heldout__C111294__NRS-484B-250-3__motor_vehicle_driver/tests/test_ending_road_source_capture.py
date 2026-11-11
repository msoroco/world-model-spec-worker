from pathlib import Path
from types import SimpleNamespace as NS
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ending_road_source_capture import EndingRoadSourceRecorder, topology_from_native
from ending_road_route import select_t_routes
from ending_road_measurement import measure


def waypoint(x, y, road, lane, junction=False):
    point = NS(road_id=road, lane_id=lane, is_junction=junction,
               transform=NS(location=NS(x=x, y=y)))
    point.get_junction = lambda: NS(id=42) if junction else None
    point.next = lambda step: []
    return point


def paths(direction=1):
    ending = [waypoint(0, -4*direction, 1, 1), waypoint(0, -2*direction, 9, 1, True),
              waypoint(0, 0, 2, 1)]
    through = [waypoint(-4*direction, 0, 3, 1), waypoint(-2*direction, 0, 10, 1, True),
               waypoint(0, 0, 3, 1)]
    for path in (ending, through):
        for first, second in zip(path, path[1:]):
            first.next = lambda step, second=second: [second]
    for point in ending:
        point.transform.get_forward_vector = lambda direction=direction: NS(x=0, y=direction)
    for point in through:
        point.transform.get_forward_vector = lambda direction=direction: NS(x=direction, y=0)
    return ending, through


def actor(ident, x, y):
    state = NS(id=ident, x=x, y=y)
    state.get_transform = lambda: NS(location=NS(x=state.x, y=state.y))
    state.bounding_box = NS(get_world_vertices=lambda _: [
        NS(x=state.x+dx, y=state.y+dy) for dx, dy in
        ((-.4,-.4),(.4,-.4),(.4,.4),(-.4,.4)) for _ in (0,1)])
    return state


class EndingRoadSourceCaptureTests(unittest.TestCase):
    def test_connected_native_paths_and_body_readbacks_feed_measurement(self):
        for direction in (1, -1):
            with self.subTest(direction=direction):
                ending, through = paths(direction)
                subject, other = actor(1, 0, -4*direction), actor(2, -4*direction, 0)
                zone = [[-1,-1],[1,-1],[1,1],[-1,1]]
                topology = topology_from_native(ending, through, subject, other, NS(id=42), zone)
                self.assertFalse(topology['legal_highway_classification_claimed'])
                with tempfile.TemporaryDirectory() as directory:
                    recorder = EndingRoadSourceRecorder(directory, topology, subject, other)
                    for frame in range(4):
                        subject.y = (-4 + frame * 2) * direction
                        other.x = (-4 + frame * 2) * direction
                        recorder.append(100 + frame, frame * .05)
                    recorder.close()
                    observation = measure(Path(directory)/'intersection_topology.json',
                                          Path(directory)/'intersection_participants.jsonl')
                    self.assertEqual(observation['subject_entry_frame'], 102)
                    self.assertEqual(observation['other_entry_frame'], 102)
                    self.assertTrue(observation['conflict_overlap_observed'])
                    with self.assertRaises(FileExistsError):
                        EndingRoadSourceRecorder(directory, topology, subject, other)

    def test_rejects_disconnected_and_nonending_native_routes(self):
        ending, through = paths()
        subject, other = actor(1, 0, -4), actor(2, -4, 0)
        zone = [[-1,-1],[1,-1],[1,1],[-1,1]]
        ending[0].next = lambda step: []
        with self.assertRaisesRegex(ValueError, 'not connected'):
            topology_from_native(ending, through, subject, other, NS(id=42), zone)
        ending, through = paths()
        ending[-1].road_id = 1
        with self.assertRaisesRegex(ValueError, 'ending-road'):
            topology_from_native(ending, through, subject, other, NS(id=42), zone)

    def test_selects_connected_transverse_paths_in_both_approach_directions(self):
        for direction in (1, -1):
            with self.subTest(direction=direction):
                ending, through = paths(direction)
                locations = {id(path[0].transform.location): path[0]
                             for path in (ending, through)}
                world_map = NS(name='FakeTown',
                               get_spawn_points=lambda: [NS(location=path[0].transform.location)
                                                         for path in (ending, through)],
                               get_waypoint=lambda location: locations[id(location)])
                selected = select_t_routes(world_map)
                self.assertEqual(selected['subject'], ending)
                self.assertEqual(selected['other'], through)
                self.assertFalse(selected['legal_highway_classification_claimed'])
                through[0].transform.get_forward_vector = lambda: NS(x=0, y=direction)
                with self.assertRaisesRegex(ValueError, 'No connected'):
                    select_t_routes(world_map)

    def test_route_keeps_spawn_approach_before_junction(self):
        ending, through = paths()
        starts = [waypoint(0, -8, 1, 1), waypoint(-8, 0, 3, 1)]
        for start, original in zip(starts, (ending, through)):
            start.next = lambda step, original=original: [original[0]]
            start.transform.get_forward_vector = original[0].transform.get_forward_vector
        locations = {id(start.transform.location): start for start in starts}
        world_map = NS(name='FakeTown',
                       get_spawn_points=lambda: [NS(location=start.transform.location) for start in starts],
                       get_waypoint=lambda location: locations[id(location)])
        selected = select_t_routes(world_map)
        self.assertIs(selected['subject'][0], starts[0])
        self.assertIs(selected['other'][0], starts[1])
        self.assertEqual(selected['subject'][2], ending[1])

    def test_rejects_turn_branch_when_same_approach_also_continues(self):
        ending, through = paths()
        continuation = waypoint(0, 2, 1, 1)
        ending[1].next = lambda step: [ending[2], continuation]
        locations = {id(path[0].transform.location): path[0]
                     for path in (ending, through)}
        world_map = NS(name='FakeTown',
                       get_spawn_points=lambda: [NS(location=path[0].transform.location)
                                                 for path in (ending, through)],
                       get_waypoint=lambda location: locations[id(location)])
        with self.assertRaisesRegex(ValueError, 'No connected'):
            select_t_routes(world_map)


if __name__ == '__main__':
    unittest.main()
