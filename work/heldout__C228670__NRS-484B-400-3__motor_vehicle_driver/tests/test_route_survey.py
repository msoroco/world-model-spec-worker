import hashlib
import importlib.util
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest


MODULE = Path(__file__).resolve().parents[1] / "route_survey.py"
spec = importlib.util.spec_from_file_location("c228670_route_survey", MODULE)
survey_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(survey_module)


def source():
    return {
        "provenance_kind": "native_xodr_survey",
        "map_name": "fixture-map",
        "intersection_kind": "public_highway_non_alley",
        "approach_directions": 2,
        "destination_directions": 1,
        "waypoints": [
            {"road_id": 1, "lane_id": -1, "s": 1, "xy_m": [0, -8]},
            {"road_id": 1, "lane_id": -1, "s": 8, "xy_m": [0, -1]},
            {"road_id": 2, "lane_id": -1, "s": 2, "xy_m": [-6, 0]},
        ],
        "approach_centerline_xy_m": [[0, -10], [0, 0]],
        "destination_left_curb_xy_m": [[0, -3], [-10, -3]],
        "intersection_entry_xy_m": [0, 0],
    }


class Map:
    name = "fixture-map"

    def __init__(self, junction=True, shift=0, opposing_approach=True, opposing_exit=False):
        self.junction, self.shift = junction, shift
        self.opposing_approach, self.opposing_exit = opposing_approach, opposing_exit

    def _waypoint(self, road_id, x, y, yaw, junction=False):
        return SimpleNamespace(road_id=road_id, lane_type="Driving",
            is_junction=junction,
            transform=SimpleNamespace(location=SimpleNamespace(x=x, y=y),
                                      rotation=SimpleNamespace(yaw=yaw)))

    def get_waypoint_xodr(self, road_id, lane_id, s):
        positions = {(1, 1): (0, -8), (1, 8): (0, -1), (2, 2): (-6, 0)}
        x, y = positions[(road_id, s)]
        return self._waypoint(road_id, x + self.shift, y,
                              90 if road_id == 1 else 180,
                              self.junction and s == 8)

    def generate_waypoints(self, spacing):
        assert spacing == 2.0
        lanes = [self._waypoint(1, 0, -8, 90), self._waypoint(2, -6, 0, 180)]
        if self.opposing_approach:
            lanes.append(self._waypoint(1, 2, -8, 270))
        if self.opposing_exit:
            lanes.append(self._waypoint(2, -6, 2, 0))
        return lanes


class RouteSurveyTests(unittest.TestCase):
    def load(self, value):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "survey.json"
            raw = json.dumps(value).encode()
            path.write_bytes(raw)
            return survey_module.load_survey(path, hashlib.sha256(raw).hexdigest())

    def test_source_and_native_junction_join(self):
        survey = self.load(source())
        self.assertEqual(len(survey_module.verify_native_route(Map(), survey, "Driving")), 3)
        with self.assertRaisesRegex(ValueError, "no interior Native junction"):
            survey_module.verify_native_route(Map(junction=False), survey, "Driving")
        with self.assertRaisesRegex(ValueError, "differs from source"):
            survey_module.verify_native_route(Map(shift=1), survey, "Driving")
        with self.assertRaisesRegex(ValueError, "lacks opposing"):
            survey_module.verify_native_route(Map(opposing_approach=False), survey, "Driving")
        with self.assertRaisesRegex(ValueError, "exit has opposing"):
            survey_module.verify_native_route(Map(opposing_exit=True), survey, "Driving")

    def test_rejects_unproved_layout_and_stale_source(self):
        value = source()
        value["provenance_kind"] = "synthetic_fixture"
        with self.assertRaisesRegex(ValueError, "XODR provenance"):
            self.load(value)
        value = source()
        value["intersection_entry_xy_m"] = [1, 0]
        with self.assertRaisesRegex(ValueError, "off the approach centerline"):
            self.load(value)
        with TemporaryDirectory() as directory:
            path = Path(directory) / "survey.json"
            path.write_text(json.dumps(source()))
            with self.assertRaisesRegex(ValueError, "hash differs"):
                survey_module.load_survey(path, "0" * 64)


if __name__ == "__main__":
    unittest.main()
