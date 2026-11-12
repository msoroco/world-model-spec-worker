"""CPU contract tests for the independent crosswalk delivery boundary."""
from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[1] / "runtime/pipeline"))
from delivery_audit import (CAMERAS, VIEW_SUBJECTS, audit,
                            check_crossing_review, check_pixel_review, sha)


def write(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value) + "\n")


class DeliveryAuditTests(unittest.TestCase):
    def shape(self, root: Path):
        attempt = root / "attempt"
        saved = root / "saved"
        decode_dir = root / "decode"
        for folder in (attempt, saved, decode_dir):
            folder.mkdir()
        case_id = HERE.name + "__reference"
        for camera in CAMERAS:
            (attempt / (camera + ".mkv")).write_bytes(camera.encode())
            write(decode_dir / (camera + ".json"), {"camera": camera})
        (attempt / "primary.mkv").write_bytes(b"source shaped primary")
        write(decode_dir / "primary.json", {"primary": True})
        write(attempt / "crosswalk-context.json",
              {"native_map_sha256": "map-source-hash"})
        write(attempt / "native-construction-context.json",
              {"native_map_sha256": "map-source-hash"})
        mapping = [{"time_s": i / 20, "video_frame": i} for i in range(240)]
        (attempt / "video_frames.jsonl").write_text(
            "".join(json.dumps(row) + "\n" for row in mapping))
        write(attempt / "core.json", {"scenes": [
            {"t": round(i / 20 * 1000)} for i in range(240)]})
        write(saved / "result.json", {
            "case_id": case_id,
            "measured_values": {"observed_crosswalk_half": "right"},
            "maneuver_completed": False, "legal_verdict_claimed": False,
            "accepted": False})
        write(saved / "processing.json", {
            "result": str(saved / "result.json"),
            "missing_evidence": False, "timestamp_joins": {"passed": True},
            "original_source_hashes": {"video_frames.jsonl":
                                       sha(attempt / "video_frames.jsonl")}})
        write(root / "owner.json", {"event": "source-shaped"})
        pixel = {"format": "c10316-source-pixel-review-v1",
                 "case_id": case_id, "frames": 240, "reviewer": "CPU test",
                 "method": "source-shaped metadata test",
                 "source_kind": "source_shaped_unit_test",
                 "legal_verdict_claimed": False,
                 "views": {camera: {
                     "video_sha256": sha(attempt / (camera + ".mkv")),
                     "subjects_visible": sorted(VIEW_SUBJECTS[camera]),
                     "reviewed_crosswalk_frames": 112, "limitations": []}
                     for camera in CAMERAS}}
        pixel_path = root / "pixel.json"
        write(pixel_path, pixel)
        facts = {name: {"observation": "source-shaped test value",
                        "source_path": "crosswalk-context.json",
                        "source_sha256": sha(attempt / "crosswalk-context.json")}
                 for name in ("signals", "passage_space", "obstacles",
                              "other_pedestrians")}
        crossing = {"format": "c10316-crossing-context-review-v1",
                    "case_id": case_id, "reviewer": "CPU test",
                    "method": "source-shaped metadata test",
                    "source_kind": "source_shaped_unit_test",
                    "crosswalk_context_sha256":
                        sha(attempt / "crosswalk-context.json"),
                    "native_construction_sha256":
                        sha(attempt / "native-construction-context.json"),
                    "native_map_sha256": "map-source-hash",
                    "marked_highway_crosswalk_confirmed": True,
                    "alley_route_connection_confirmed": True,
                    "practicability_judgment": "unverified",
                    "legal_verdict_claimed": False, "facts": facts}
        crossing_path = root / "crossing.json"
        write(crossing_path, crossing)
        return (attempt, saved, root / "owner.json", case_id,
                pixel_path, crossing_path, decode_dir)

    def test_source_shaped_review_and_nonpromotion(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (attempt, saved, owner, case_id,
             pixel, crossing, decode_dir) = self.shape(root)
            self.assertEqual(check_pixel_review(pixel, attempt, case_id,
                                                test_shape=True)["frames"], 240)
            self.assertEqual(check_crossing_review(crossing, attempt, case_id,
                                                   test_shape=True)
                             ["practicability_judgment"], "unverified")
            motion = {"source_shaped_motion_status": "met",
                      "native_motion_status": "unverified",
                      "source_sha256": {"video_frames.jsonl":
                                        sha(attempt / "video_frames.jsonl")}}
            with patch("delivery_audit.lifecycle_audit",
                       return_value={"capture_seal_sha256": "test-seal"}), \
                 patch("delivery_audit.motion_audit", return_value=motion), \
                 patch("scenario_pipeline.worker_exchange.media.audit",
                       return_value={"auditor_sha256": "test-decoder"}):
                result = audit(attempt, saved, owner, case_id, "test-construction",
                               pixel, crossing, attempt / "primary.mkv",
                               attempt / "core.json", decode_dir,
                               test_shape=True)
            self.assertFalse(result["passed"])
            self.assertEqual(result["motion_status"], "unverified")
            self.assertEqual(result["practicability_judgment"], "unverified")

    def test_changed_sources_and_production_label_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (attempt, saved, owner, case_id,
             pixel, crossing, decode_dir) = self.shape(root)
            with self.assertRaisesRegex(ValueError, "Original crosswalk pixel"):
                check_pixel_review(pixel, attempt, case_id)
            (attempt / "overview.mkv").write_bytes(b"changed")
            with self.assertRaisesRegex(ValueError, "pixels unreviewed"):
                check_pixel_review(pixel, attempt, case_id, test_shape=True)
            write(attempt / "crosswalk-context.json",
                  {"native_map_sha256": "changed"})
            with self.assertRaisesRegex(ValueError, "crosswalk or route context"):
                check_crossing_review(crossing, attempt, case_id,
                                      test_shape=True)


if __name__ == "__main__":
    unittest.main()
