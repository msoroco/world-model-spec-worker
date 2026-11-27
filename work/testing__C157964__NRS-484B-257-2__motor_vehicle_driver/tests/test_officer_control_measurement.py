"""Synthetic fixtures test source admission; they are not physical evidence."""

from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[3]
SOURCE = Path(__file__).resolve().parents[1] / "officer_control_measurement.py"
SPEC = importlib.util.spec_from_file_location("officer_control_measurement", SOURCE)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
SCRATCH = REPO / ".runtime-work/c157964-officer-tests"
SCRATCH.mkdir(parents=True, exist_ok=True)


class OfficerControlTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=SCRATCH)
        self.root = Path(self.temp.name)
        self.packet = {
            "assignment_id": MODULE.ASSIGNMENT,
            "cell_id": "C157964",
            "law_id": "NRS-484B-257-2",
            "actor": "motor_vehicle_driver",
            "recording_id": "original-fixture-id",
        }
        self.add("original_video", b"synthetic-video-bytes")
        self.add("native_result", {"source_kind": "original_native",
                                   "assignment_id": MODULE.ASSIGNMENT,
                                   "recording_id": "original-fixture-id"})
        self.add("frame_map", [{"frame": i, "elapsed_s": i / 20} for i in range(900)])
        self.add("officer_review", {"source_kind": "original_independent_review",
                                    "recording_id": "original-fixture-id",
                                    "reviewer_id": "fixture reviewer",
                                    "source_video_sha256": self.packet["original_video"]["sha256"],
                                    "crossing_interval_frames": [300, 360],
                                    "officer_visible": True,
                                    "officer_controlling_traffic": True})

    def tearDown(self):
        self.temp.cleanup()

    def add(self, key, data):
        raw = data if isinstance(data, bytes) else json.dumps(data).encode()
        name = key + (".bin" if isinstance(data, bytes) else ".json")
        (self.root / name).write_bytes(raw)
        self.packet[key] = {"path": name, "sha256": hashlib.sha256(raw).hexdigest()}

    def test_observed_control_context(self):
        value = MODULE.measure(self.packet, self.root)
        self.assertEqual(value["exception_context"], "observed_officer_control")
        self.assertIsNone(value["legal_verdict"])

    def test_presence_without_control_separated(self):
        review = json.loads((self.root / "officer_review.json").read_text())
        review["officer_controlling_traffic"] = False
        self.add("officer_review", review)
        self.assertEqual(MODULE.measure(self.packet, self.root)["exception_context"],
                         "officer_present_not_controlling")

    def test_video_change_rejected(self):
        (self.root / "original_video.bin").write_bytes(b"changed")
        with self.assertRaisesRegex(ValueError, "hash differs"):
            MODULE.measure(self.packet, self.root)

    def test_rehashed_frame_gap_rejected(self):
        frames = json.loads((self.root / "frame_map.json").read_text())
        frames[355]["frame"] = 356
        self.add("frame_map", frames)
        with self.assertRaisesRegex(ValueError, "contiguous"):
            MODULE.measure(self.packet, self.root)

    def test_unseen_controlling_officer_rejected(self):
        review = json.loads((self.root / "officer_review.json").read_text())
        review["officer_visible"] = False
        self.add("officer_review", review)
        with self.assertRaisesRegex(ValueError, "visibility"):
            MODULE.measure(self.packet, self.root)


if __name__ == "__main__":
    unittest.main()
