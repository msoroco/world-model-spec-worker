import sys
import json
import hashlib
import tempfile
import types
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from native_walking import run_walking_route, run_constructed, world_route


class Walker:
    def __init__(self):
        self.x = self.y = 0.0
        self.control = None
        self.controls = []

    def get_transform(self):
        return types.SimpleNamespace(location=types.SimpleNamespace(x=self.x, y=self.y))

    def apply_control(self, command):
        self.control = command
        self.controls.append(command)


class World:
    def __init__(self, walker, mode="moving"):
        self.walker, self.mode, self.frame = walker, mode, 100

    def tick(self):
        self.frame += 1
        control = self.walker.control
        if self.mode != "stalled":
            self.walker.x += control["direction"]["x"] * control["speed"] / 20
            self.walker.y += control["direction"]["y"] * control["speed"] / 20
        if self.mode == "depart" and self.frame == 103:
            self.walker.y += 2.0
        return self.frame

    def get_map(self):
        return types.SimpleNamespace(name="reviewed-map")

    def get_snapshot(self):
        seconds = self.frame / 20 + (.2 if self.mode == "stale" and self.frame >= 103 else 0)
        return types.SimpleNamespace(frame=self.frame,
                                     timestamp=types.SimpleNamespace(elapsed_seconds=seconds))


CARLA = types.SimpleNamespace(Vector3D=lambda **kw: kw, WalkerControl=lambda **kw: kw)
ROUTE = [(0, 0), (2, 0), (2, 2)]


class WalkingTests(unittest.TestCase):
    def test_completes_original_measured_route_and_stops(self):
        walker = Walker()
        observed = []
        rows = run_walking_route(World(walker), walker, CARLA, ROUTE, speed_m_s=2,
                                 on_sample=observed.append)
        self.assertEqual(len(rows), 900)
        self.assertEqual(rows, observed)
        self.assertTrue(rows[-1]["route_completed"])
        self.assertLess(abs(rows[-1]["position_world_xy_m"][1] - 2), .25)
        self.assertEqual(walker.controls[-1]["speed"], 0)

    def test_observation_failure_stops_walker(self):
        walker = Walker()
        def fail(sample):
            raise ValueError("camera source unavailable")
        with self.assertRaisesRegex(ValueError, "camera source unavailable"):
            run_walking_route(World(walker), walker, CARLA, ROUTE,
                              speed_m_s=2, on_sample=fail)
        self.assertEqual(walker.controls[-1]["speed"], 0)

    def test_stall_departure_and_time_gap_fail_closed(self):
        for mode, message in [("stalled", "measured-motion"),
                              ("depart", "departed"),
                              ("stale", "continuity")]:
            with self.subTest(mode=mode):
                walker = Walker()
                with self.assertRaisesRegex(ValueError, message):
                    run_walking_route(World(walker, mode), walker, CARLA, ROUTE,
                                      speed_m_s=2)
                self.assertEqual(walker.controls[-1]["speed"], 0)

    def test_rejects_unsurveyed_start_and_bad_contract(self):
        walker = Walker()
        walker.x = 1
        with self.assertRaisesRegex(ValueError, "start"):
            run_walking_route(World(walker), walker, CARLA, ROUTE)
        walker.x = 0
        with self.assertRaisesRegex(ValueError, "20 Hz"):
            run_walking_route(World(walker), walker, CARLA, ROUTE, frames=899)

    def test_constructed_case_binds_survey_and_transformed_route(self):
        case = "testing__C104081__NRS-484B-297-6__pedestrian__clear_intervening"
        survey = {"map_id": "reviewed-map", "local_to_world":
                  {"x": 0, "y": 0, "yaw_degrees": 0}}
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "survey.json"
            path.write_text(json.dumps(survey))
            constructed = {"case_id": case, "site_map_id": "reviewed-map",
                           "survey_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                           "route_local_xy_m": [list(point) for point in ROUTE]}
            self.assertEqual(world_route(ROUTE, survey["local_to_world"]), ROUTE)
            walker = Walker()
            rows = run_constructed(World(walker), walker, CARLA, constructed,
                                   path, case, speed_m_s=2)
            self.assertEqual(len(rows), 900)
            path.write_text(json.dumps(dict(survey, map_id="different")))
            with self.assertRaisesRegex(ValueError, "stale survey"):
                run_constructed(World(Walker()), Walker(), CARLA, constructed,
                                path, case)


if __name__ == "__main__":
    unittest.main()
