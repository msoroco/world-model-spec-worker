"""Source-shaped audit protocol tests; fixtures carry no review authority."""
import hashlib
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from delivery_audit import audit
from reviewed_scene import ASSIGNMENT, CAMERAS


class DeliveryAuditTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(dir=os.environ["SCENARIO_PIPELINE_OUTPUT_ROOT"])
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.case = ASSIGNMENT + "__slow_middle_follower"
        self.scene = {"map_sha256": "a" * 64, "rightmost_lane_id": "-1",
                      "actors": [{"lane_id": "-2"}], "requested_immediate_follower": True}
        self.observations = [{"ego_in_extreme_right_lane": False,
                              "follower_immediately_behind_in_ego_lane": True,
                              "follower_closing_speed_mps": 3.0} for _ in range(900)]
        frames = [{"frame": i, "native_frame": i + 100, "time_s": i / 20,
                   "camera_frames": {name: i + 100 for name in CAMERAS}}
                  for i in range(900)]
        self.frame_map = {"source_kind": "original_native_frame_map", "case_id": self.case,
                          "frames": frames}
        self.receipt = {"case_id": self.case, "source_kind": "original_native_attempt",
                        "native_process_exit_code": 0, "owner_released": True,
                        "attempt_id": "fixture-attempt", "recording_id": "fixture-recording",
                        "site_ref": {"path": "site.json", "sha256": "b" * 64}}
        self.receipt["frame_map_ref"] = self.save("frame-map.json", self.frame_map)
        self.receipt["trace_ref"] = self.save("trace.json", {"fixture": True})
        self.receipt["relation_ref"] = self.save("relation.json", {"fixture": True})
        self.receipt["video_refs"] = {name: self.save(name + ".bin", "diagnostic-bytes") for name in CAMERAS}
        self.seal = {"source_kind": "original_native_capture_seal", "case_id": self.case,
                     "attempt_id": "fixture-attempt", "recording_id": "fixture-recording",
                     "sources": {ref["path"]: ref["sha256"] for ref in
                                 [self.receipt["site_ref"], self.receipt["frame_map_ref"],
                                  self.receipt["trace_ref"], self.receipt["relation_ref"],
                                  *self.receipt["video_refs"].values()]}}
        self.receipt["capture_seal_ref"] = self.save("seal.json", self.seal)
        self.probe = lambda path: {"nb_read_frames": "900", "r_frame_rate": "20/1",
                                   "width": "960", "height": "540"}
        self.patch_plan = patch("delivery_audit.plan", return_value=self.scene)
        self.patch_final = patch("delivery_audit.finalize", return_value={"observations": self.observations})
        self.patch_plan.start()
        self.patch_final.start()
        self.addCleanup(self.patch_plan.stop)
        self.addCleanup(self.patch_final.stop)

    def save(self, name, content):
        path = self.root / name
        path.write_text(json.dumps(content) + "\n" if isinstance(content, dict) else content)
        return {"path": name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}

    def test_complete_original_protocol(self):
        result = audit(self.root, self.receipt, self.probe)
        self.assertEqual(result["frames_checked"], 900)
        self.assertEqual(len(result["video_sha256"]), 4)
        self.assertEqual(result["legal_impediment_and_pass_necessity"], "unresolved")

    def test_rejects_diagnostic_and_unreleased_attempt(self):
        self.receipt["diagnostic_fixture"] = True
        with self.assertRaisesRegex(ValueError, "released original"):
            audit(self.root, self.receipt, self.probe)
        self.receipt["diagnostic_fixture"] = False
        self.receipt["owner_released"] = False
        with self.assertRaisesRegex(ValueError, "released original"):
            audit(self.root, self.receipt, self.probe)

    def test_rejects_frame_gap_and_video_hash_change(self):
        self.frame_map["frames"].pop()
        self.receipt["frame_map_ref"] = self.save("frame-map.json", self.frame_map)
        self.seal["sources"]["frame-map.json"] = self.receipt["frame_map_ref"]["sha256"]
        self.receipt["capture_seal_ref"] = self.save("seal.json", self.seal)
        with self.assertRaisesRegex(ValueError, "900-frame"):
            audit(self.root, self.receipt, self.probe)
        self.frame_map["frames"].append({"frame": 899, "native_frame": 999,
            "time_s": 899 / 20, "camera_frames": {name: 999 for name in CAMERAS}})
        self.receipt["frame_map_ref"] = self.save("frame-map.json", self.frame_map)
        self.seal["sources"]["frame-map.json"] = self.receipt["frame_map_ref"]["sha256"]
        self.receipt["capture_seal_ref"] = self.save("seal.json", self.seal)
        (self.root / "overview.bin").write_text("tampered")
        with self.assertRaisesRegex(ValueError, "hash changed"):
            audit(self.root, self.receipt, self.probe)

    def test_rejects_short_decode_and_wrong_lane_readback(self):
        def short_probe(path):
            return {"nb_read_frames": "899", "r_frame_rate": "20/1", "width": "960", "height": "540"}
        with self.assertRaisesRegex(ValueError, "full decode"):
            audit(self.root, self.receipt, short_probe)
        self.observations[0]["ego_in_extreme_right_lane"] = True
        with self.assertRaisesRegex(ValueError, "realized lane"):
            audit(self.root, self.receipt, self.probe)

    def test_rejects_missing_reviewed_site_and_unrealized_pass(self):
        with patch("delivery_audit.plan", side_effect=ValueError("original reviewed highway site missing")):
            with self.assertRaisesRegex(ValueError, "reviewed highway site missing"):
                audit(self.root, self.receipt, self.probe)
        self.scene["requested_passing_slower_vehicle"] = True
        for row in self.observations:
            row["passing_slower_vehicle_observed"] = False
        with self.assertRaisesRegex(ValueError, "requested pass not observed"):
            audit(self.root, self.receipt, self.probe)

    def test_rejects_changed_capture_seal(self):
        self.seal["sources"]["trace.json"] = "0" * 64
        self.receipt["capture_seal_ref"] = self.save("seal.json", self.seal)
        with self.assertRaisesRegex(ValueError, "sealed original source inventory"):
            audit(self.root, self.receipt, self.probe)


if __name__ == "__main__":
    unittest.main()
