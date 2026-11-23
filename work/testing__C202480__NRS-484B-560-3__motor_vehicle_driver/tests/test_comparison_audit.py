"""CPU checks of all planned isolation pairs and missing evidence rejection."""

import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parents[1]
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
from comparison_audit import compare
from runner import retain_site_sources
import test_native_scene as scene_fixture


class ComparisonAuditTests(unittest.TestCase):
    def setUp(self):
        private = ROOT / ".runtime-work"
        private.mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=private)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.fixture = scene_fixture.NativeSceneTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.plan = json.loads((HERE / "case-plan.json").read_text())
        self.cases = {case["case_id"]: case for case in self.fixture.cases}

    def pair(self, item):
        attempts = []
        for index, case_id in enumerate(item["case_ids"]):
            attempt = self.root / (item["comparison_id"] + "-" + str(index))
            attempt.mkdir()
            packet_path, _ = self.fixture.packet(self.cases[case_id])
            retain_site_sources(attempt, packet_path, self.fixture.plan, case_id)
            attempts.append(attempt)
        return attempts

    def geometry(self, attempt):
        packet = json.loads((attempt / "site/packet.json").read_text())
        case = self.cases[packet["case_id"]]
        return {"case_id": packet["case_id"],
                "legal_judgment": "unresolved",
                "two_queue_aligned_frame_count": 30 if case["traffic_arrangement"] == "two_queues" else 0,
                "minimum_stopped_lateral_offset_from_reviewed_rightmost_m":
                    3. if case["subject_lateral_plan"] == "left_of_feasible" else 0.}

    def test_all_exact_pairs_check_fixed_and_changed_conditions(self):
        for item in self.plan["comparisons"]:
            with self.subTest(comparison=item["comparison_id"]):
                left, right = self.pair(item)
                result = compare(left, right, item["comparison_id"],
                                 geometry_auditor=self.geometry)
                self.assertEqual(result["case_ids"], item["case_ids"])
                self.assertFalse(result["physical_acceptance_claimed"])

    def test_missing_queue_observation_rejected(self):
        item = self.plan["comparisons"][0]
        left, right = self.pair(item)
        def absent(attempt):
            result = self.geometry(attempt)
            result["two_queue_aligned_frame_count"] = 0
            return result
        with self.assertRaisesRegex(ValueError, "queue arrangement contrast absent"):
            compare(left, right, item["comparison_id"], geometry_auditor=absent)

    def test_changed_fixed_opendrive_rejected(self):
        item = self.plan["comparisons"][0]
        left, right = self.pair(item)
        source = right / "site/opendrive.txt"
        source.write_text("<OpenDRIVE><road id='different'/></OpenDRIVE>")
        packet_path = right / "site/packet.json"
        packet = json.loads(packet_path.read_text())
        packet["sources"]["opendrive"]["sha256"] = hashlib.sha256(source.read_bytes()).hexdigest()
        packet_path.write_text(json.dumps(packet))
        with self.assertRaisesRegex(ValueError, "fixed reviewed highway geometry differs"):
            compare(left, right, item["comparison_id"],
                    geometry_auditor=self.geometry)

    def test_above_boundary_pair_rejects_missing_fifth_marked_lane(self):
        item = next(c for c in self.plan["comparisons"]
                    if c["comparison_id"] == "marked_lane_above_boundary")
        left, right = self.pair(item)
        packet_path = right / "site/packet.json"
        packet = json.loads(packet_path.read_text())
        packet["marked_lanes"] = packet["marked_lanes"][:4]
        marking = right / "site/lane_markings.txt"
        marking.write_text(json.dumps({"marked_lanes": packet["marked_lanes"]}))
        packet["sources"]["lane_markings"]["sha256"] = hashlib.sha256(marking.read_bytes()).hexdigest()
        packet_path.write_text(json.dumps(packet))
        with self.assertRaisesRegex(ValueError, "total marked highway lane count differs"):
            compare(left, right, item["comparison_id"], geometry_auditor=self.geometry)


if __name__ == "__main__":
    unittest.main()
