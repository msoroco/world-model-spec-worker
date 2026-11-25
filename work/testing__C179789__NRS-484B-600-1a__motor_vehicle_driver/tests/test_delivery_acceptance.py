"""Negative boundaries for independent Native and pixel acceptance."""

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import delivery_acceptance as ACCEPT


class DeliveryAcceptanceTests(unittest.TestCase):
    CASE = ACCEPT.ASSIGNMENT + "__dry_open_traffic"

    def test_missing_sealed_original_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            attempt = Path(temporary)
            (attempt / "result.json").write_text(json.dumps({
                "case_id": self.CASE, "provenance_kind": "native",
                "diagnostic_fixture": False}) + "\n")
            (attempt / "capture-seal.json").write_text(json.dumps({
                "provenance_kind": "native", "diagnostic_fixture": False,
                "restoration": {"restored": True}, "sources": {}}) + "\n")
            with self.assertRaisesRegex(ValueError, "seal omits original"):
                ACCEPT.verify_originals(attempt, self.CASE)

    def test_reviewed_pixel_actor_must_match_original_history(self):
        with tempfile.TemporaryDirectory() as temporary:
            attempt = Path(temporary)
            frame_map = attempt / "video_frames.jsonl"
            frame_map.write_text('{"video_frame":0,"carla_frame":10,"time_s":0.5}\n')
            source_hashes = {}
            for camera in ACCEPT.CAMERAS:
                source = attempt / (camera + ".mkv")
                source.write_bytes(b"fixture camera bytes")
                source_hashes[camera] = ACCEPT.sha(source)
            review = attempt / "pixel-review.json"
            observations = []
            for camera in ACCEPT.CAMERAS:
                observations.extend([
                    {"camera": camera, "actor": "ego", "actor_id": 999,
                     "video_frame": 0, "bbox_xyxy": [0, 0, 2, 2]},
                    {"camera": camera, "actor": "lead", "actor_id": 2,
                     "video_frame": 0, "bbox_xyxy": [0, 0, 2, 2]},
                ])
            review.write_text(json.dumps({
                "case_id": self.CASE, "reviewer": "diagnostic fixture reviewer",
                "method": "independent pixel identity test",
                "frame_map_sha256": ACCEPT.sha(frame_map),
                "source_sha256": source_hashes,
                "observations": observations}) + "\n")
            (attempt / "config.json").write_text(json.dumps({
                "cameras": [{"name": name, "width": 4, "height": 4}
                            for name in ACCEPT.CAMERAS]}) + "\n")
            history = [{"ego_actor_id": 1,
                        "surrounding_traffic": [{"actor_id": 2}]}]

            def decode(_, __, checkers=None, **___):
                if checkers:
                    frame = type("Frame", (), {"index": 0, "width": 4,
                                               "height": 4,
                                               "pixels": bytes(range(48))})()
                    checkers["reviewed_actor_pixels"][1](frame)

            with patch.object(ACCEPT, "verify_originals", return_value=([{}], history)), \
                    patch("delivery_audit.audit_delivery", return_value={}), \
                    patch("worker_exchange.media.audit", side_effect=decode):
                with self.assertRaisesRegex(ValueError, "Reviewed actor identity differs"):
                    ACCEPT.audit(attempt, self.CASE, review, attempt / "acceptance.json")


if __name__ == "__main__":
    unittest.main()
