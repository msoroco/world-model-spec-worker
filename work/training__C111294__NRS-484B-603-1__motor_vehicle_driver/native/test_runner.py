"""CPU checks of the proposed Native controller and measured fallback path."""
from __future__ import annotations

import hashlib
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from engineering import CASES, CANDIDATES, candidate_plan, evaluate_fallback, target_mph
from runner import check, control_command

FIXTURES = HERE.parent / "draft-fixtures"


class NativeApproachTests(unittest.TestCase):
    def test_all_constructions_have_distinct_preflights(self):
        for case in CASES:
            plans = [candidate_plan(case, candidate) for candidate in CANDIDATES]
            self.assertEqual(len({p["construction_sha256"] for p in plans}), 4)
            for candidate, plan in zip(CANDIDATES, plans):
                self.assertTrue(check(case, candidate)["passed"])
                self.assertEqual(plan["candidate"], candidate)

    def test_control_profile_and_braking_response(self):
        self.assertEqual(target_mph("probe_a", "primary", 70), 30)
        self.assertAlmostEqual(target_mph("probe_a", "primary", 40), 25)
        self.assertEqual(target_mph("probe_a", "primary", 10), 20)
        self.assertEqual(target_mph("probe_b", "primary", 10), 30)
        knobs = candidate_plan("probe_a", "primary")["knobs"]
        hold = control_command(30*.44704, 0, 0, 30, knobs)
        reduced = control_command(30*.44704, 0, 0, 20, knobs)
        self.assertEqual(hold["brake"], 0)
        self.assertGreater(reduced["brake"], 0)

    def test_fallback_reads_hashed_saved_source(self):
        fixtures = {"probe_a": "decrease", "probe_b": "hold"}
        for case, name in fixtures.items():
            path = FIXTURES / f"{name}-synthetic-native.jsonl"
            sha = hashlib.sha256(path.read_bytes()).hexdigest()
            self.assertFalse(evaluate_fallback(case, "primary", path, sha)["triggered"])
            with self.assertRaisesRegex(ValueError, "source hash changed"):
                evaluate_fallback(case, "primary", path, "0"*64)
        wrong = FIXTURES / "hold-synthetic-native.jsonl"
        wrong_sha = hashlib.sha256(wrong.read_bytes()).hexdigest()
        choice = evaluate_fallback("probe_a", "primary", wrong, wrong_sha)
        self.assertTrue(choice["triggered"])
        self.assertEqual(choice["next_candidate"], "fallback1")
        choice = evaluate_fallback("probe_a", "fallback3", wrong, wrong_sha)
        self.assertTrue(choice["exhausted"])
        self.assertEqual(choice["next_candidate"], "fallback3")

    def test_three_fallbacks_have_distinct_measured_conditions(self):
        cases = {
            "probe_a": [
                ("primary", "fallback1", {"approach_start_mph": 30, "preentry_mph": 28,
                                          "decrease_mph": 2, "crossing_peak_mph": 20}, "decrease_mph"),
                ("fallback1", "fallback2", {"approach_start_mph": 30, "preentry_mph": 20,
                                            "decrease_mph": 10, "crossing_peak_mph": 29}, "crossing_peak_mph"),
                ("fallback2", "fallback3", {"approach_start_mph": 30, "preentry_mph": 22,
                                            "decrease_mph": 8, "crossing_peak_mph": 20}, "preentry_mph")],
            "probe_b": [
                ("primary", "fallback1", {"approach_start_mph": 30, "preentry_mph": 28.5,
                                          "decrease_mph": 1.5, "crossing_peak_mph": 30}, "decrease_mph"),
                ("fallback1", "fallback2", {"approach_start_mph": 28, "preentry_mph": 28,
                                            "decrease_mph": 0, "crossing_peak_mph": 30}, "approach_start_mph"),
                ("fallback2", "fallback3", {"approach_start_mph": 30, "preentry_mph": 30,
                                            "decrease_mph": 0, "crossing_peak_mph": 28}, "crossing_peak_mph")]}
        for case, checks in cases.items():
            for current, next_id, measured, metric in checks:
                with self.subTest(case=case, next_id=next_id):
                    with patch("measure_approach.measure", return_value={
                        **measured, "measured_relation": "measured_ambiguous_decrease",
                        "source_sha256": "a" * 64}):
                        result = evaluate_fallback(case, current, Path("unused"), "a" * 64)
                    self.assertTrue(result["triggered"])
                    self.assertEqual(result["next_candidate"], next_id)
                    self.assertEqual(result["metric"], metric)
                    self.assertEqual(result["observed"], measured[metric])


if __name__ == "__main__":
    unittest.main()
