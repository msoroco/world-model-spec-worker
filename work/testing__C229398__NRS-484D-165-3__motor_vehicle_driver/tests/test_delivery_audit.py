import json
import pathlib
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT.parents[1] / "runtime" / "scenario_pipeline"))
import delivery_audit as audit


class DeliveryAuditTest(unittest.TestCase):
    def test_source_bound_diagnostic_and_rejection(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            case = audit.ASSIGNMENT + "__dark_lamps_on"
            (root / "result.json").write_text(json.dumps({
                "recording_description": {"channels": []},
                "trace_reference": "trace.jsonl", "video_frame_map_reference": "video_frames.jsonl"}))
            (root / "capture-seal.json").write_text(json.dumps({
                "format": "worker-sealed-capture", "provenance_kind": "native", "frames": 900,
                "restoration": {"restored": True},
                "events": ["capture_finished", "encoders_closed", "restoration_verified"],
                "sources": {"result.json": audit.sha(root / "result.json")}}))
            (root / "video_frames.jsonl").write_text("".join(
                json.dumps({"video_frame": i, "time_s": i / 20}) + "\n" for i in range(900)))
            (root / "core.json").write_text(json.dumps({
                "scenes": [{"t": round(i * 50)} for i in range(900)]}))
            (root / "primary.mkv").write_bytes(b"diagnostic video placeholder")
            review = root / "pixel-review.json"
            pixel = {"case_id": case, "source_result_sha256": audit.sha(root / "result.json"),
                     "video_sha256": audit.sha(root / "primary.mkv"),
                     "frame_map_sha256": audit.sha(root / "video_frames.jsonl"),
                     "reviewer": "CPU fixture", "method": "synthetic binding check",
                     "source_frames_reviewed": [0, 899], "parked_interval_verified": True,
                     "diagnostic_fixture": True, "actual_original_pixels": False,
                     "front_white_or_amber_500ft": "unknown", "rear_red_500ft": "unknown",
                     "revelation_1000ft": "unknown", "traffic_side_installation": "unknown"}
            review.write_text(json.dumps(pixel))
            receipt = root / "decode.json"
            def fake_decode(*_args, **kwargs):
                pathlib.Path(kwargs["receipt"]).write_text("{}\n")
                return {"auditor_sha256": "f" * 64}
            with patch.object(audit, "decode_video", side_effect=fake_decode):
                result = audit.review(root, case, review, "primary.mkv", "core.json", receipt,
                                      diagnostic=True)
                self.assertFalse(result["passed"])
                with self.assertRaisesRegex(ValueError, "physical original-pixel review required"):
                    audit.review(root, case, review, "primary.mkv", "core.json", receipt)
                pixel["video_sha256"] = "0" * 64
                review.write_text(json.dumps(pixel))
                with self.assertRaisesRegex(ValueError, "pixel review source binding differs"):
                    audit.review(root, case, review, "primary.mkv", "core.json", receipt,
                                 diagnostic=True)


if __name__ == "__main__":
    unittest.main()
