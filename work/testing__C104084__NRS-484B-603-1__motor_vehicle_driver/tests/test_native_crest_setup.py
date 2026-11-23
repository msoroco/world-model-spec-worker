import hashlib
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from native_crest_setup import load_and_bind


PACKAGE = Path(__file__).resolve().parents[1]
MAP = PACKAGE / 'candidate-crest-road.xodr'
FILE_HASH = hashlib.sha256(MAP.read_bytes()).hexdigest()


class Waypoint:
    lane_type = 'LaneType.Driving'

    def __init__(self, station, lane_id):
        self.road_id, self.lane_id, self.s = 603, lane_id, station
        z = .032 * station - .000064 * station ** 2
        self.transform = SimpleNamespace(location=SimpleNamespace(
            x=station, y=lane_id * 1.75, z=z))
        self.following = []

    def next(self, distance):
        return self.following


def lane(stations, lane_id):
    points = [Waypoint(station, lane_id) for station in stations]
    for left, right in zip(points, points[1:]):
        left.following = [right]
    return points[0]


class Map:
    name = 'C104084 two-way hill crest candidate'

    def __init__(self, source):
        self.source = source

    def to_opendrive(self):
        return self.source

    def get_waypoint_xodr(self, road_id, lane_id, station):
        if road_id != 603:
            return None
        if lane_id == -1 and station == 230:
            return lane(range(230, 271, 5), -1)
        if lane_id == 1 and station == 270:
            return lane(range(270, 229, -5), 1)
        return None


class Client:
    def __init__(self, source):
        self.source = source
        self.loads = []

    def generate_opendrive_world(self, source):
        self.loads.append(source)
        return SimpleNamespace(get_map=lambda: Map(self.source))


class NativeCrestSetupTests(unittest.TestCase):
    def test_loads_exact_file_and_binds_two_actual_native_directions(self):
        client = Client(MAP.read_text())
        result = load_and_bind(client, MAP, expected_file_sha256=FILE_HASH)
        self.assertEqual(len(client.loads), 1)
        self.assertEqual(result['map_file_sha256'], FILE_HASH)
        self.assertEqual(result['routes']['binding']['forward_lane_id'], -1)
        self.assertEqual(result['routes']['binding']['opposing_lane_id'], 1)
        self.assertAlmostEqual(result['routes']['binding']['crest_separation_m'], 3.5)
        self.assertEqual(result['routes']['forward']['crest_world_xyz_m'][0], 250)

    def test_rejects_wrong_file_hash_before_native_load(self):
        client = Client(MAP.read_text())
        with self.assertRaisesRegex(ValueError, 'file hash differs'):
            load_and_bind(client, MAP, expected_file_sha256='0' * 64)
        self.assertEqual(client.loads, [])

    def test_rejects_loaded_grade_substitution(self):
        client = Client(MAP.read_text().replace('c="-0.000064"', 'c="0"'))
        with self.assertRaisesRegex(ValueError, 'loaded Native crest geometry differs'):
            load_and_bind(client, MAP, expected_file_sha256=FILE_HASH)


if __name__ == '__main__':
    unittest.main()
