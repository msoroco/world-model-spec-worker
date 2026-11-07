import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from geometry import check, route
from engineering import evaluate_trigger, parameters
from controller import EngineeringKnobs, PathController
from runner import observed_speed_mps


class NativeParkingUnit(unittest.TestCase):
    def test_observed_speed_uses_current_velocity_and_rejects_nonfinite(self):
        class Actor:
            velocity = SimpleNamespace(x=3, y=4, z=0)
            def get_velocity(self):
                return self.velocity

        actor = Actor()
        self.assertEqual(observed_speed_mps(actor), 5)
        actor.velocity = SimpleNamespace(x=0, y=0, z=2)
        self.assertEqual(observed_speed_mps(actor), 2)
        actor.velocity = SimpleNamespace(x=float('inf'), y=0, z=0)
        with self.assertRaisesRegex(ValueError, 'Nonfinite observed Native velocity'):
            observed_speed_mps(actor)

    def test_controlled_full_body(self):
        proof = check()["probes"]
        self.assertEqual(proof["probe_a"]["authored_intersection_overlap_m2"], 0)
        self.assertGreater(proof["probe_b"]["authored_intersection_overlap_m2"], 10)

    def test_controller_requests_stop_at_observed_endpoint(self):
        path = route("probe_a")
        controller = PathController(path, 2.8, 35.0, EngineeringKnobs())
        controller.last_index = len(path) - 1
        output = controller.step(position_xy_m=tuple(path[-1]), yaw_rad=0,
                                 speed_mps=0, dt_s=.05)
        self.assertTrue(output["hand_brake"])
        self.assertEqual(output["requested_speed_mps"], 0)

    def test_three_distinct_law_preserving_knobs(self):
        base = parameters("probe_b", "primary")["knobs"]
        changes = []
        for candidate in ("fallback1", "fallback2", "fallback3"):
            value = parameters("probe_b", candidate)["knobs"]
            changes.append({key for key in base if value[key] != base[key]})
            self.assertEqual((value["rate_hz"], value["duration_s"]), (20, 24))
        self.assertEqual(changes, [{"route_lookahead_m"},
                                   {"parking_brake_margin_m"},
                                   {"overview_fov_deg"}])

    def test_trigger_rejects_source_mutation(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "metrics.json"
            path.write_text(json.dumps({"source_kind": "original_native_and_video",
                                        "max_cross_track_error_m": .6}))
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            self.assertTrue(evaluate_trigger("fallback1", path, digest))
            path.write_text(path.read_text() + " ")
            with self.assertRaisesRegex(ValueError, "hash differs"):
                evaluate_trigger("fallback1", path, digest)


if __name__ == "__main__": unittest.main()
