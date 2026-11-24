"""Original-frame feature provenance and negative source-join tests."""

import hashlib
import json
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
import feature_review
from saved_measurement import sha
from owner_release import release
from test_saved_measurement import SavedMeasurementTests


class FeatureReviewTests(unittest.TestCase):
    def setUp(self):
        fixture = SavedMeasurementTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        self.attempt = fixture.attempt
        self.case_id = fixture.case_id
        packet_path = self.attempt / "site/packet.json"
        packet = json.loads(packet_path.read_text())
        for camera in packet["cameras"]:
            camera["pose_source_citation"] = "reviewed original map camera position"
            camera["reviewer"] = "site reviewer"
        packet_path.write_text(json.dumps(packet))
        status_path = self.attempt / "native-run-status.json"
        status = json.loads(status_path.read_text())
        status["site_packet_sha256"] = sha(packet_path)
        status_path.write_text(json.dumps(status))
        exit_path = self.attempt / "native-exit.json"
        exited = json.loads(exit_path.read_text())
        exited["native_run_status_sha256"] = sha(status_path)
        exit_path.write_text(json.dumps(exited))
        (self.attempt / "owner-release.json").unlink()
        release(self.attempt, liveness_probe=lambda _: False)
        self.packet = packet
        self.raw = bytes([20, 40, 60, 255, 100, 120, 140, 255,
                          50, 70, 90, 255, 150, 170, 190, 255])
        raw_path = self.attempt / "raw/overview/00001000.bgra"
        raw_path.parent.mkdir(parents=True)
        raw_path.write_bytes(self.raw)
        video = self.attempt / "overview.mkv"
        subprocess.run(["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error",
                        "-f", "rawvideo", "-pixel_format", "bgra",
                        "-video_size", "2x2", "-framerate", "20", "-i", "pipe:0",
                        "-frames:v", "1", "-an", "-c:v", "ffv1", "-pix_fmt",
                        "bgra", "-y", str(video)], input=self.raw, check=True)
        mapping = self.attempt / "video_frames.jsonl"
        rows = [json.loads(line) for line in mapping.read_text().splitlines()]
        rows[0]["camera_source_sha256"]["overview"] = sha(raw_path)
        mapping.write_text("".join(json.dumps(row) + "\n" for row in rows))
        media_path = self.attempt / "media-receipt.json"
        media = json.loads(media_path.read_text())
        media["video_sha256"]["overview"] = sha(video)
        media_path.write_text(json.dumps(media))
        crop_hash = hashlib.sha256(self.raw).hexdigest()
        annotations = []
        for name in feature_review.FEATURES:
            source = packet["sources"][feature_review.SOURCE_FOR_FEATURE[name]]
            annotations.append({"feature": name, "view": "overview",
                                "video_frame": 0, "carla_frame": 1000,
                                "camera_source_sha256": sha(raw_path),
                                "site_source_sha256": source["sha256"],
                                "bbox_xyxy": [0, 0, 2, 2],
                                "bgra_frame_sha256": crop_hash,
                                "bgra_crop_sha256": crop_hash,
                                "observation": "uncertain", "reviewer": "reviewer A"})
        self.review = {"format": "c202480-original-feature-review-v1",
                       "case_id": self.case_id,
                       "native_status_sha256": sha(self.attempt / "native-run-status.json"),
                       "site_packet_sha256": sha(packet_path),
                       "frame_map_sha256": sha(mapping),
                       "media_receipt_sha256": sha(media_path),
                       "annotations": annotations}
        self.review_path = self.attempt / "feature-review.json"
        self.save()
        self.view_patch = patch.object(feature_review, "VIEWS", (("overview", 2, 2),
            ("approach", 1280, 720), ("reference_corner", 1280, 720),
            ("driver_reference", 1280, 720)))
        self.view_patch.start()
        self.addCleanup(self.view_patch.stop)

    def save(self):
        self.review_path.write_text(json.dumps(self.review))

    def test_original_pixel_and_source_bound_review(self):
        result = feature_review.verify(self.attempt, self.review_path)
        self.assertEqual(len(result["annotations"]), 6)
        self.assertFalse(result["feature_visibility_verified"])
        self.assertEqual(result["legal_judgment"], "unresolved")

    def test_changed_video_rejected(self):
        with (self.attempt / "overview.mkv").open("ab") as stream:
            stream.write(b"changed")
        with self.assertRaisesRegex(ValueError, "video bytes differ"):
            feature_review.verify(self.attempt, self.review_path)

    def test_changed_raw_camera_rejected(self):
        (self.attempt / "raw/overview/00001000.bgra").write_bytes(b"changed")
        with self.assertRaisesRegex(ValueError, "raw camera hash differs"):
            feature_review.verify(self.attempt, self.review_path)

    def test_diagnostic_camera_citation_rejected(self):
        path = self.attempt / "site/packet.json"
        packet = json.loads(path.read_text())
        packet["cameras"][0]["pose_source_citation"] = "synthetic fixture camera pose"
        path.write_text(json.dumps(packet))
        status_path = self.attempt / "native-run-status.json"
        status = json.loads(status_path.read_text())
        status["site_packet_sha256"] = sha(path)
        status_path.write_text(json.dumps(status))
        exit_path = self.attempt / "native-exit.json"
        exited = json.loads(exit_path.read_text())
        exited["native_run_status_sha256"] = sha(status_path)
        exit_path.write_text(json.dumps(exited))
        (self.attempt / "owner-release.json").unlink()
        release(self.attempt, liveness_probe=lambda _: False)
        self.review["site_packet_sha256"] = sha(path)
        self.review["native_status_sha256"] = sha(status_path)
        self.save()
        with self.assertRaisesRegex(ValueError, "diagnostic camera poses"):
            feature_review.verify(self.attempt, self.review_path)

    def test_bad_feature_crop_rejected(self):
        self.review["annotations"][0]["bgra_crop_sha256"] = "0" * 64
        self.save()
        with self.assertRaisesRegex(ValueError, "crop bytes differ"):
            feature_review.verify(self.attempt, self.review_path)

    def test_missing_feature_rejected(self):
        self.review["annotations"].pop()
        self.save()
        with self.assertRaisesRegex(ValueError, "one annotation"):
            feature_review.verify(self.attempt, self.review_path)


if __name__ == "__main__":
    unittest.main()
