"""Exercise independent original-source joins with synthetic source-shaped packets."""

import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from delivery_audit import ASSIGNMENT, VIEWS, audit


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class DeliveryAuditTests(unittest.TestCase):
    def setUp(self):
        scratch = Path(os.environ["SCENARIO_PIPELINE_OUTPUT_ROOT"])
        self.temp = tempfile.TemporaryDirectory(dir=scratch, prefix="c380107-audit-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.case = ASSIGNMENT + "__core_no_hov"
        self.refs = {}

    def write(self, name, data):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(data, dict):
            path.write_text(json.dumps(data, sort_keys=True) + "\n", encoding="utf-8")
        else:
            path.write_bytes(data)
        ref = {"path": name, "sha256": digest(path)}
        self.refs[name] = ref
        return ref

    def attempt(self):
        frame_refs = [self.write("pixels/%d.png" % n, bytes([n])) for n in range(3)]
        videos = {view: self.write("video/" + view + ".mp4", view.encode()) for view in VIEWS}
        frames = []
        rows = []
        for n in range(900):
            image_ref = frame_refs[0 if n < 450 else (1 if n < 899 else 2)]
            frames.append({"frame": n, "time_s": n / 20, "native_frame": n + 100,
                           "camera_frames": {view: dict(image_ref, native_frame=n + 100)
                                             for view in VIEWS}})
            rows.append({"frame": n, "time_s": n / 20, "native_frame": n + 100})
        site = self.write("site.json", {"source_kind": "original_site_fixture"})
        frame_map = self.write("frame-map.json", {"source_kind": "original_native_frame_map",
                                                  "case_id": self.case, "frames": frames})
        trace = self.write("trace.jsonl", ("\n".join(json.dumps(row) for row in rows) + "\n").encode())
        context = self.write("context.json", {"case_id": self.case})
        original_receipt = self.write("original-receipt.json", {"case_id": self.case})
        seal_sources = {ref["path"]: ref["sha256"] for ref in
                        [site, frame_map, trace, context, original_receipt, *videos.values()]}
        seal = self.write("seal.json", {"source_kind": "original_native_capture_seal",
                                        "case_id": self.case, "attempt_id": "fixture-attempt",
                                        "recording_id": "fixture-recording", "sources": seal_sources})
        return {"case_id": self.case, "source_kind": "original_native_attempt",
                "owner_released": True, "native_process_exit_code": 0,
                "attempt_id": "fixture-attempt", "recording_id": "fixture-recording",
                "site_ref": site, "frame_map_ref": frame_map, "trace_ref": trace,
                "context_ref": context, "original_receipt_ref": original_receipt,
                "video_refs": videos, "capture_seal_ref": seal}

    @staticmethod
    def probe(_):
        return {"nb_read_frames": "900", "r_frame_rate": "20/1",
                "width": "1920", "height": "1080"}

    @staticmethod
    def fake_pixels(paths):
        return len(paths) == 12

    def run_audit(self, receipt):
        def profile_probe(path):
            from package_contract import CAMERAS
            view = path.stem
            camera = next(item for item in CAMERAS if item["name"] == view)
            return {"nb_read_frames": "900", "r_frame_rate": "20/1",
                    "width": camera["width"], "height": camera["height"]}
        measured = {"first_rear_gap_crossing_frame": 200, "posted_limit_mps": 9.0,
                    "extreme_left_lane_id": "L0", "hov_designation_state_source_label": "none",
                    "hov_compliance_state_source_label": "unresolved"}
        with patch("delivery_audit.plan", return_value={}), patch(
                "delivery_audit.observe", return_value=measured):
            return audit(self.root, receipt, probe=profile_probe,
                         decode=lambda _: True, pixels=self.fake_pixels)

    def test_original_source_joins_and_decode_protocol(self):
        receipt = self.attempt()
        result = self.run_audit(receipt)
        self.assertEqual(result["frames_checked"], 900)
        self.assertEqual(set(result["video_sha256"]), set(VIEWS))
        self.assertEqual(result["legal_verdict"], "unresolved")

    def test_unreleased_attempt_is_rejected(self):
        receipt = self.attempt()
        receipt["owner_released"] = False
        with self.assertRaisesRegex(ValueError, "released original"):
            self.run_audit(receipt)

    def test_stale_frame_or_video_is_rejected(self):
        receipt = self.attempt()
        (self.root / "video/overview.mp4").write_bytes(b"changed")
        with self.assertRaisesRegex(ValueError, "hash changed"):
            self.run_audit(receipt)

    def test_out_of_sync_frame_is_rejected(self):
        receipt = self.attempt()
        path = self.root / "frame-map.json"
        packet = json.loads(path.read_text())
        packet["frames"][400]["camera_frames"][VIEWS[0]]["native_frame"] = 999
        path.write_text(json.dumps(packet, sort_keys=True) + "\n")
        receipt["frame_map_ref"]["sha256"] = digest(path)
        seal_path = self.root / "seal.json"
        seal = json.loads(seal_path.read_text())
        seal["sources"]["frame-map.json"] = receipt["frame_map_ref"]["sha256"]
        seal_path.write_text(json.dumps(seal, sort_keys=True) + "\n")
        receipt["capture_seal_ref"]["sha256"] = digest(seal_path)
        with self.assertRaisesRegex(ValueError, "camera native frame"):
            self.run_audit(receipt)


if __name__ == "__main__":
    unittest.main()
