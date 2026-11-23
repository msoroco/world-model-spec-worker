"""CPU checks of independent crossing qualification and source rejection."""

import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from crossing_branch_audit import REQUIRED, audit


class CrossingBranchAuditTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        sources = {}
        for name in REQUIRED:
            path = self.root / (name + ".json")
            path.write_text(json.dumps({"synthetic_fixture": name}) + "\n")
            sources[name] = {"path": path.name,
                             "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
        self.packet = {"sources": sources, "stopping_required": True,
                       "marked_highway_lane_count": 2,
                       "traffic_queue_arrangement": "two_queues",
                       "right_side_feasibility": "rightmost_feasible"}
        self.path = self.root / "packet.json"

    def check(self):
        self.path.write_text(json.dumps(self.packet) + "\n")
        return audit(self.path)

    def test_two_lanes_and_four_lane_qualification_are_separate(self):
        two = self.check()
        self.assertTrue(two["two_queue_prohibition_context"])
        self.assertFalse(two["marked_four_or_more_qualification"])
        self.packet["marked_highway_lane_count"] = 4
        self.packet["right_side_feasibility"] = "left_of_feasible"
        four = self.check()
        self.assertFalse(four["two_queue_prohibition_context"])
        self.assertTrue(four["marked_four_or_more_qualification"])
        self.assertEqual(four["right_side_evidence"], "left_of_feasible")
        self.assertTrue(four["right_side_duty_remains_independent"])
        self.assertEqual(four["legal_judgment"], "unresolved")

    def test_missing_or_changed_source_rejected(self):
        self.check()
        (self.root / "vehicle_footprints.json").unlink()
        with self.assertRaisesRegex(ValueError, "changed or absent source"):
            audit(self.path)

    def test_unreviewed_stop_or_arrangement_rejected(self):
        self.packet["stopping_required"] = None
        with self.assertRaisesRegex(ValueError, "supported crossing stop"):
            self.check()
        self.packet["stopping_required"] = True
        self.packet["traffic_queue_arrangement"] = "abreast"
        with self.assertRaisesRegex(ValueError, "reviewed traffic queue"):
            self.check()
