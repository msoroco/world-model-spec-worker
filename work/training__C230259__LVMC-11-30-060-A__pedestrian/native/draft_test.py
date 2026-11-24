import json
from pathlib import Path
import unittest
from runner import check, request, survey


class FakeCarla:
    class LaneType:
        Driving = 'driving'

    class Location:
        def __init__(self, x, y, z):
            self.x, self.y, self.z = x, y, z


class FakeWaypoint:
    def __init__(self, y, lane_id):
        self.road_id = 1
        self.lane_id = lane_id
        self.transform = type('T', (), {'location': FakeCarla.Location(-1.75, y, 0)})()


class FakeMap:
    def __init__(self, wrong=False):
        self.wrong = wrong

    def to_opendrive(self):
        return Path('road.xodr').read_text()

    def get_waypoint(self, location, project_to_road, lane_type):
        return FakeWaypoint(location.y, -1 if self.wrong else 1)


class FakeWorld:
    def __init__(self, wrong=False):
        self.mapping = FakeMap(wrong)

    def get_map(self):
        return self.mapping


class Draft(unittest.TestCase):
    def setUp(self):
        self.config = json.loads(Path("config.json").read_text())

    def test_exact_contract(self):
        result = check(self.config)
        self.assertEqual(result["frames"], 600)
        expected = 320 if self.config["case_id"].endswith("probe_01") else 140
        self.assertEqual(request(0, self.config["case_id"])["pedestrian_departure_frame"], expected)
        self.assertEqual(request(expected, self.config["case_id"])["pedestrian_target_speed_mps"], 1.2)

    def test_native_survey_gate(self):
        self.assertEqual(len(survey(FakeWorld(), FakeCarla)['roadway_samples']), 4)
        with self.assertRaisesRegex(RuntimeError, 'Native roadway lane survey differs'):
            survey(FakeWorld(wrong=True), FakeCarla)

    def test_wrong_identity_and_frame_rejected(self):
        bad = dict(self.config, cell_id="C0")
        with self.assertRaisesRegex(ValueError, "frozen identity"):
            check(bad)
        with self.assertRaisesRegex(ValueError, "600-frame"):
            request(600, self.config["case_id"])


if __name__ == "__main__":
    unittest.main()
