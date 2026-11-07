"""Saved synthetic CPU positives and adversarial negatives for C111294 speed."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import tempfile
import unittest

import geometry
import measure_speed
import engineering


class GeometrySpeedTest(unittest.TestCase):
    def test_authored_long_route(self):
        result = geometry.check()
        self.assertTrue(result["passed"])
        self.assertFalse(result["physical_speed_observed"])

    def _measure(self, raw: bytes, **kwargs):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "native_samples.jsonl"
            path.write_bytes(raw)
            return measure_speed.measure(path, hashlib.sha256(raw).hexdigest(), **kwargs)

    def test_three_controlled_speed_settings(self):
        expected = {75: "measured_not_above_80_mph",
                    79.5: "measured_not_above_80_mph",
                    85: "measured_above_80_mph"}
        for mph, relation in expected.items():
            with self.subTest(mph=mph):
                report = self._measure(measure_speed.synthetic_fixture(mph))
                self.assertEqual(report["measured_relation"], relation)
                self.assertAlmostEqual(report["derived_peak_mph"], mph, places=5)
                self.assertIsNone(report["legal_verdict"])

    def test_boundary_uncertainty_is_unresolved(self):
        report = self._measure(measure_speed.synthetic_fixture(80))
        self.assertEqual(report["measured_relation"], "unresolved_at_80_mph")

    def test_changed_hash_rejected(self):
        raw = measure_speed.synthetic_fixture(85)
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "samples.jsonl"
            path.write_bytes(raw)
            wrong = hashlib.sha256(b"other source").hexdigest()
            with self.assertRaisesRegex(ValueError, "hash changed"):
                measure_speed.measure(path, wrong)

    def test_missing_frame_rejected(self):
        raw = measure_speed.synthetic_fixture(85)
        with self.assertRaisesRegex(ValueError, "480"):
            self._measure(b"\n".join(raw.splitlines()[:-1]) + b"\n")

    def test_actor_collision_and_missing_motion_rejected(self):
        rows = [json.loads(line) for line in measure_speed.synthetic_fixture(85).splitlines()]
        rows[100]["other_actor_id"] = rows[100]["ego_actor_id"]
        bad = "".join(json.dumps(r) + "\n" for r in rows).encode()
        with self.assertRaisesRegex(ValueError, "distinct actor IDs"):
            self._measure(bad)
        rows[100]["other_actor_id"] = 202
        for row in rows:
            row["other_position_m"][1] = 100
        bad = "".join(json.dumps(r) + "\n" for r in rows).encode()
        with self.assertRaisesRegex(ValueError, "route or motion absent"):
            self._measure(bad)

    def test_velocity_and_time_negatives(self):
        rows = [json.loads(line) for line in measure_speed.synthetic_fixture(85).splitlines()]
        rows[80]["ego_velocity_mps"] = [0, float("nan"), 0]
        bad = "".join(json.dumps(r) + "\n" for r in rows).encode()
        with self.assertRaisesRegex(ValueError, "velocity component"):
            self._measure(bad)
        rows[80]["ego_velocity_mps"] = [0, 85 / measure_speed.MPS_TO_MPH, 0]
        rows[80]["t_s"] += .01
        bad = "".join(json.dumps(r) + "\n" for r in rows).encode()
        with self.assertRaisesRegex(ValueError, "timestamp"):
            self._measure(bad)

    def test_velocity_pose_disagreement_rejected(self):
        rows = [json.loads(line) for line in measure_speed.synthetic_fixture(85).splitlines()]
        rows[200]["ego_velocity_mps"] = [0, 30, 0]
        bad = "".join(json.dumps(r) + "\n" for r in rows).encode()
        with self.assertRaisesRegex(ValueError, "Velocity and pose"):
            self._measure(bad)

    def _gate(self, case, candidate, raw):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "native_samples.jsonl"
            path.write_bytes(raw)
            return engineering.evaluate(case, candidate, path, hashlib.sha256(raw).hexdigest())

    def test_four_distinct_plans_hold_case_and_context(self):
        plans = [engineering.candidate_plan("above_80_mph", c)
                 for c in engineering.CANDIDATES]
        self.assertEqual(len({tuple(sorted(p["changed_knobs"])) for p in plans}), 4)
        for key in ("case_id", "law_id", "cell_id", "actor",
                    "comparison_variable", "requested_setting_mph",
                    "fixed_authored_road", "fixed_other_actor_route"):
            self.assertEqual(len({p[key] for p in plans}), 1)
        self.assertTrue(all(p["status"] == "unselected_draft" for p in plans))

    def test_source_measured_fallback_gates(self):
        case = "above_80_mph"
        baseline = measure_speed.synthetic_fixture(85)
        for candidate in engineering.GATES:
            self.assertFalse(self._gate(case, candidate, baseline)["triggered"])
        self.assertTrue(self._gate(case, "fallback1",
                                   measure_speed.synthetic_fixture(84))["triggered"])
        self.assertTrue(self._gate(case, "fallback3",
                                   measure_speed.synthetic_fixture(86))["triggered"])
        rows = [json.loads(line) for line in baseline.splitlines()]
        for row in rows:
            row["ego_position_m"][0] = 2.2
        shifted = "".join(json.dumps(r) + "\n" for r in rows).encode()
        self.assertTrue(self._gate(case, "fallback2", shifted)["triggered"])
        with self.assertRaisesRegex(ValueError, "Gate source hash changed"):
            with tempfile.TemporaryDirectory() as temp:
                path = Path(temp) / "native_samples.jsonl"
                path.write_bytes(shifted)
                engineering.evaluate(case, "fallback2", path,
                                     hashlib.sha256(baseline).hexdigest())


if __name__ == "__main__":
    unittest.main(verbosity=2)
