"""The physical CPU protocol must measure motion and reject altered sources."""
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from physical_proof import evaluate, history_for, scene_for
from parking_pose import REQUESTS


class PhysicalProofTests(unittest.TestCase):
    def test_all_exact_motion_outcomes(self):
        with TemporaryDirectory() as temp:
            path = Path(temp) / "history.jsonl"
            for suffix in REQUESTS:
                scene = scene_for(suffix)
                for kind, status in (("complete_motion", "met"),
                                     ("incomplete_motion", "not_met")):
                    path.write_text("".join(json.dumps(row) + "\n"
                                            for row in history_for(scene, kind)))
                    result = evaluate(suffix, kind, path)
                    self.assertEqual(result["physical_checks"]["maneuver"]["status"],
                                     status)
                    self.assertFalse(result["physical_acceptance_claimed"])
                path.unlink()
                self.assertEqual(evaluate(suffix, "missing_evidence", path)
                                 ["physical_checks"]["maneuver"]["status"],
                                 "unverified")

    def test_shortened_approach_cannot_pass_complete_probe(self):
        with TemporaryDirectory() as temp:
            path = Path(temp) / "history.jsonl"
            suffix = "park_parallel_lawful"
            path.write_text("".join(json.dumps(row) + "\n" for row in
                                    history_for(scene_for(suffix), "incomplete_motion")))
            with self.assertRaisesRegex(ValueError, "measured physical outcome differs"):
                evaluate(suffix, "complete_motion", path)
            with self.assertRaisesRegex(ValueError, "retained original history"):
                evaluate(suffix, "missing_evidence", path)


if __name__ == "__main__":
    unittest.main()
