"""CPU checks of the proposed Native controller and measured fallback path."""
from __future__ import annotations

import hashlib
from pathlib import Path
import sys
import unittest

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


if __name__ == "__main__":
    unittest.main()
