from __future__ import annotations

from copy import deepcopy
import json
import importlib.util
from pathlib import Path
import tempfile
import unittest

MODULE = Path(__file__).with_name("yield_branch_comparison.py")
spec = importlib.util.spec_from_file_location("yield_branch_comparison", MODULE)
comparison = importlib.util.module_from_spec(spec)
spec.loader.exec_module(comparison)
FINALIZER = Path(__file__).with_name("native") / "yield_branch_finalize.py"
finalizer_spec = importlib.util.spec_from_file_location("yield_branch_finalize", FINALIZER)
finalizer = importlib.util.module_from_spec(finalizer_spec)
finalizer_spec.loader.exec_module(finalizer)


def row(index, policy):
    if index < 80:
        x, y, speed = 1.75, -41 + .3 * index, 6.0
    elif index < 130:
        x, y, speed = 1.75, -17.0, 0.0
    elif index < 160:
        x, y, speed = 1.75, -17 + .3 * (index - 130), 6.0
    else:
        start = 190 if policy == "yield_wait" else 160
        if index < start:
            x, y, speed = 1.75, -8.0, 0.0
        else:
            progress = min((index - start) / 20, 1.0)
            x = 1.75 + 8.25 * progress
            y = -8 + 6.25 * progress
            speed = 6.0 if index < start + 20 else 1.0
            if index >= start + 20:
                x += (index - start - 20) * .02
    occupied = 145 <= index <= 180
    walker = [10.0, 0.0 if occupied else 5.0]
    body = [[x - 1, y - 2], [x - 1, y + 2],
            [x + 1, y - 2], [x + 1, y + 2]]
    return {"native_frame": index + 1000, "time_s": index / 20,
            "native_center_xy_m": [x, y], "native_body_xy_m": body,
            "native_yaw_deg": 90.0, "speed_mps": speed,
            "walker_center_xy_m": walker,
            "walker_conflict_occupied": occupied,
            "signal_state_observed": "Red", "yield_policy": policy,
            "yield_decision_reason": ("pedestrian_conflict_occupied" if policy == "yield_wait"
                                      else "deliberate_conflict_entry_probe"),
            "controller_request": {"brake": 1.0 if speed == 0 else 0.0},
            "synthetic_diagnostic": True,
            "speed_provenance": "synthetic_native_sample"}


def pair():
    return ([row(i, "yield_wait") for i in range(480)],
            [row(i, "yield_conflict_entry") for i in range(480)])


class YieldComparisonTest(unittest.TestCase):
    def test_diagnostic_overlap_comparison(self):
        result = comparison.compare(*pair(), diagnostic=True)
        self.assertTrue(result["source_comparison_passed"])
        self.assertFalse(result["original_delivery_accepted"])
        self.assertEqual(result["wait"]["body_pedestrian_overlap_frames"], [])
        self.assertTrue(result["entry"]["body_pedestrian_overlap_frames"])
        self.assertGreaterEqual(result["different_frame_range"][0], 145)

    def test_reject_changed_walker_context(self):
        wait, entry = pair()
        entry[160]["walker_center_xy_m"] = [10.0, 1.0]
        with self.assertRaisesRegex(ValueError, "Held Native"):
            comparison.compare(wait, entry, diagnostic=True)

    def test_reject_missing_shared_stop(self):
        wait, entry = pair()
        for group in (wait, entry):
            for item in group[80:130]:
                item["speed_mps"] = 1.0
        with self.assertRaisesRegex(ValueError, "stop absent"):
            comparison.compare(wait, entry, diagnostic=True)

    def test_reject_forged_occupancy(self):
        wait, entry = pair()
        entry[160]["walker_conflict_occupied"] = False
        with self.assertRaisesRegex(ValueError, "occupancy flag"):
            comparison.compare(wait, entry, diagnostic=True)

    def test_reject_diagnostic_as_original(self):
        with self.assertRaisesRegex(ValueError, "Diagnostic source"):
            comparison.compare(*pair(), diagnostic=False)

    def test_reject_undeclared_difference(self):
        wait, entry = pair()
        entry[160]["unknown_context"] = "changed"
        with self.assertRaisesRegex(ValueError, "Undeclared"):
            comparison.compare(wait, entry, diagnostic=True)

    def test_saved_finalizer_remeasures_both_branches(self):
        with tempfile.TemporaryDirectory() as temporary:
            for samples, suffix, expected in zip(pair(), comparison.POLICIES,
                                                 (False, True)):
                attempt = Path(temporary) / suffix
                attempt.mkdir()
                path = attempt / "native_samples.jsonl"
                path.write_text("".join(json.dumps(item) + "\n" for item in samples))
                measured = finalizer.measure_yield_branch(attempt, samples, suffix)
                self.assertEqual(bool(measured["value"]["body_pedestrian_overlap_frames"]),
                                 expected)
                self.assertEqual(measured["sources"]["native_samples.jsonl"],
                                 comparison.sha(path))
                self.assertEqual(comparison.load_source(path, comparison.sha(path)), samples)
                with self.assertRaisesRegex(ValueError, "hash"):
                    comparison.load_source(path, "0" * 64)

    def test_saved_finalizer_rejects_wrong_policy(self):
        wait, _ = pair()
        with tempfile.TemporaryDirectory() as temporary:
            attempt = Path(temporary)
            (attempt / "native_samples.jsonl").write_text("[]\n")
            wait[160]["yield_policy"] = "yield_conflict_entry"
            with self.assertRaisesRegex(ValueError, "policy differs"):
                finalizer.measure_yield_branch(attempt, wait, "yield_wait")


if __name__ == "__main__":
    unittest.main()
