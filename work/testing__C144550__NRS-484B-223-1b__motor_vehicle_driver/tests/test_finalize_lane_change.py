import hashlib
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from finalize_lane_change import finalize
from lane_change_timing import ASSIGNMENT


class FinalizerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(dir=os.environ["SCENARIO_PIPELINE_OUTPUT_ROOT"])
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.case = ASSIGNMENT + "__both_observed"
        anchors = [{"frame": i, "t_s": i * .05} for i in range(900)]
        self.packets = {
            "frame_map": {"samples": anchors},
            "ego_pose": {"source_lane_id": "source-lane", "lane_geometry_source": "original-map-lane",
                "samples": [{**r, "x_m": float(i), "y_m": 0.,
                             "source_lane_offset_m": .06 if i >= 4 else 0.}
                            for i, r in enumerate(anchors)]},
            "native_signal": {"readback_source": "original-signal-api",
                "samples": [{**r, "left_signal": i >= 1, "right_signal": False}
                            for i, r in enumerate(anchors)]},
            "driver_check": {"readback_source": "separate-original-driver-control",
                "observation_method": "source-event-readback",
                "samples": [{**r, "driver_check_observed": i == 2}
                            for i, r in enumerate(anchors)]},
        }
        self.inventory = {"case_id": self.case, "source_kind": "original_native",
                          "original_trace_id": "test-original-id", "sources": {}}
        self.write()

    def write(self):
        for name, packet in self.packets.items():
            packet["case_id"] = self.case
            packet["source_kind"] = "original_native"
            raw = (json.dumps(packet) + "\n").encode()
            (self.root / (name + ".json")).write_bytes(raw)
            self.inventory["sources"][name] = {"path": name + ".json",
                "sha256": hashlib.sha256(raw).hexdigest()}

    def test_joins_separate_original_check_and_signal(self):
        result = finalize(self.root, self.inventory, self.case)
        self.assertEqual(result["original_frame_count"], 900)
        self.assertEqual(result["signal_lead_distance_m"], 3.)
        self.assertTrue(result["driver_check_observed_before_departure"])
        self.assertEqual(result["driver_check_readback_source"],
                         "separate-original-driver-control")
        self.assertEqual(result["legal_ascertainment_and_safety"], "unresolved")

    def test_missing_check_source_is_rejected(self):
        self.packets["driver_check"]["readback_source"] = ""
        self.write()
        with self.assertRaisesRegex(ValueError, "independent lane, signal and driver-check"):
            finalize(self.root, self.inventory, self.case)

    def test_missing_check_observation_stays_false(self):
        for row in self.packets["driver_check"]["samples"]:
            row["driver_check_observed"] = False
        self.write()
        result = finalize(self.root, self.inventory, self.case)
        self.assertFalse(result["driver_check_observed_before_departure"])
        self.assertTrue(result["signal_precedes_center_departure"])

    def test_hash_or_frame_substitution_is_rejected(self):
        (self.root / "driver_check.json").write_text("{}")
        with self.assertRaisesRegex(ValueError, "source hash mismatch"):
            finalize(self.root, self.inventory, self.case)
        self.packets["driver_check"]["samples"][2]["frame"] = 3
        self.write()
        with self.assertRaisesRegex(ValueError, "frame/time join"):
            finalize(self.root, self.inventory, self.case)

    def test_check_packet_cannot_override_signal_readback(self):
        for row in self.packets["driver_check"]["samples"]:
            row["left_signal"] = False
        self.write()
        self.assertTrue(finalize(self.root, self.inventory, self.case)[
            "signal_precedes_center_departure"])


if __name__ == "__main__":
    unittest.main()
