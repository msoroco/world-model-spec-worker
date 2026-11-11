"""CPU preflight and original-shaped schema tests; no CARLA execution."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from types import SimpleNamespace as N
import tempfile
import unittest

import engineering
import measure_speed
import runner


class FakeActor:
    def __init__(self, ident, role, x, y, vy):
        self.id = ident
        self.type_id = "vehicle.tesla.model3"
        self.attributes = {"role_name": role}
        self.transform = N(location=N(x=x, y=y, z=.5), rotation=N(yaw=-90 if vy < 0 else 90))
        self.velocity = N(x=0, y=vy, z=0)
        self.bounding_box = N(get_world_vertices=lambda transform: [
            N(x=x-1, y=y-2, z=.1), N(x=x+1, y=y-2, z=.1),
            N(x=x+1, y=y+2, z=1.5), N(x=x-1, y=y+2, z=1.5)])

    def get_transform(self):
        return self.transform

    def get_velocity(self):
        return self.velocity

    def get_control(self):
        return N(throttle=.5, brake=0, steer=0)


class RunnerTest(unittest.TestCase):
    def test_all_twelve_cpu_preflights(self):
        for case in ("below_80_mph", "inside_80_mph", "at_80_mph", "above_80_mph"):
            for candidate in engineering.CANDIDATES:
                with self.subTest(case=case, candidate=candidate):
                    report = runner.check(case, candidate)
                    self.assertEqual(report["camera_profile"]["frames_per_view"], 480)
                    self.assertEqual(len(report["channels"]), 4)
                    self.assertFalse(report["selected"])

    def test_distinct_controls_are_wired(self):
        base = engineering.candidate_plan("above_80_mph", "primary")["knobs"]
        speed = 80 * .44704
        stronger = engineering.candidate_plan("above_80_mph", "fallback1")["knobs"]
        self.assertGreater(runner.control_command(speed, 0, 0, 85, stronger)["throttle"],
                           runner.control_command(speed, 0, 0, 85, base)["throttle"])
        wider = engineering.candidate_plan("above_80_mph", "fallback2")["knobs"]
        self.assertLess(abs(runner.control_command(speed, .5, 0, 85, wider)["steer"]),
                        abs(runner.control_command(speed, .5, 0, 85, base)["steer"]))
        brakes = engineering.candidate_plan("above_80_mph", "fallback3")["knobs"]
        self.assertGreater(runner.control_command(90*.44704, 0, 0, 85, brakes)["brake"],
                           runner.control_command(90*.44704, 0, 0, 85, base)["brake"])

    def test_native_sample_reads_actor_roles_and_velocity(self):
        ego = FakeActor(101, "c111294_speed_subject", 1.75, 70, -38)
        other = FakeActor(202, "c111294_opposing_vehicle", -1.75, -100, 10)
        row = runner.native_sample(0, 1234, .05, ego, other)
        self.assertEqual(row["ego_velocity_mps"], [0, -38, 0])
        self.assertEqual(row["native_frame"], 1234)
        self.assertEqual(row["source_kind"], "original_native_capture")
        self.assertEqual(len(row["ego_body_vertices_m"]), 4)
        other.attributes["role_name"] = "wrong"
        with self.assertRaisesRegex(ValueError, "role readback"):
            runner.native_sample(0, 1234, .05, ego, other)

    def test_original_shaped_source_requires_role_readback(self):
        rows = [json.loads(line) for line in measure_speed.synthetic_fixture(85).splitlines()]
        for row in rows:
            row["source_kind"] = "original_native_capture"
            row["ego_role_name"] = "c111294_speed_subject"
            row["other_role_name"] = "c111294_opposing_vehicle"
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "samples.jsonl"
            raw = "".join(json.dumps(r) + "\n" for r in rows).encode()
            path.write_bytes(raw)
            result = measure_speed.measure(path, hashlib.sha256(raw).hexdigest())
            self.assertEqual(result["source_kind"], "original_native_capture")
            rows[80]["ego_role_name"] = "wrong"
            raw = "".join(json.dumps(r) + "\n" for r in rows).encode()
            path.write_bytes(raw)
            with self.assertRaisesRegex(ValueError, "role readback"):
                measure_speed.measure(path, hashlib.sha256(raw).hexdigest())

    def test_reflected_lane_survey(self):
        class Carla:
            LaneType = N(Driving=1)
            Location = staticmethod(lambda **kwargs: N(**kwargs))

        class Mapping:
            def get_waypoint(self, point, **kwargs):
                if point.y > 0:
                    road, lane, direction = 1, -1, -1
                else:
                    road, lane, direction = 4, 1, 1
                return N(road_id=road, lane_id=lane, lane_width=3.5,
                         transform=N(location=N(x=point.x, y=point.y),
                                     get_forward_vector=lambda: N(x=0, y=direction)))

        report = runner._survey(Carla, Mapping())
        self.assertEqual(report["ego"]["lane_id"], -1)
        self.assertEqual(report["other"]["lane_id"], 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
