import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRATCH = ROOT.parents[1] / ".runtime-work" / "c125714-2031-physical-tests"
sys.path.insert(0, str(ROOT))
from physical_completion import assess
from test_opposing_pass import history


class PhysicalCompletionTests(unittest.TestCase):
    def setUp(self):
        SCRATCH.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=SCRATCH)
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "opposing-actor-trace.json"

    def write(self, trace):
        self.path.write_text(json.dumps(trace) + "\n")
        return hashlib.sha256(self.path.read_bytes()).hexdigest()

    def test_complete_incomplete_and_missing_source(self):
        digest = self.write(history())
        complete = assess(self.path, digest)
        self.assertEqual(complete["physical_checks"]["maneuver"]["status"], "met")
        self.assertTrue(complete["maneuver_completed"])
        self.assertFalse(complete["physical_acceptance_claimed"])
        trace = history()
        for row in trace["samples"]:
            row["other_body_s_bounds_m"] = [20, 22]
        digest = self.write(trace)
        incomplete = assess(self.path, digest)
        self.assertEqual(incomplete["physical_checks"]["maneuver"]["status"], "not_met")
        self.assertFalse(incomplete["maneuver_completed"])
        self.path.unlink()
        missing = assess(self.path, digest)
        self.assertEqual(missing["physical_checks"]["maneuver"]["status"], "unverified")

    def test_changed_hash_is_unverified(self):
        digest = self.write(history())
        self.path.write_text("{}\n")
        self.assertEqual(assess(self.path, digest)["physical_checks"]["maneuver"]["status"],
                         "unverified")


if __name__ == "__main__":
    unittest.main()
