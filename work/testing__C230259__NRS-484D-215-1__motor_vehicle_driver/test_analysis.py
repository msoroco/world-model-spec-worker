"""Run saved-only analysis on source-shaped CPU evidence and reject stale joins."""
from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from analysis import build
from test_beam_measure import fixture as motion_fixture
from test_beam_pixels import _fixture as pixel_fixture

ROOT = Path(__file__).resolve().parent
TEMP_ROOT = ROOT.parents[1] / ".runtime-work" / "c230259-analysis-tests"
CASE = next(x for x in json.loads((ROOT / "case-plan.json").read_text())["cases"]
            if x["case_id"].endswith("__oncoming_499_low"))
VIEWS = ("overview", "approach", "reference_corner", "driver_reference")


def _hash(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fixture(root):
    pixel_fixture(root, 9, start_frame=1732)
    motion_fixture(root, 9)
    site_path = root / "site-packet.json"
    site = json.loads(site_path.read_text())
    site.update({"case_id": CASE["case_id"], "requested_beam": CASE["requested_beam"],
                 "requested_contour": CASE["requested_contour"],
                 "requested_load": CASE["requested_load"],
                 "requested_start_body_gap_ft": CASE["requested_start_body_gap_ft"]})
    site_path.write_text(json.dumps(site) + "\n")
    config = {"assignment_id": ROOT.name, "law_id": "NRS-484D-215-1",
              "selected_case_id": CASE["case_id"], "case_plan": CASE}
    (root / "config.json").write_text(json.dumps(config) + "\n")
    movies = {}
    for view in VIEWS:
        path = root / (view + ".mkv")
        path.write_text("diagnostic movie placeholder; source hash only\n")
        movies[view] = {"path": path.name, "sha256": _hash(path), "source_frame_count": 9}
    source_hashes = {name: _hash(root / name) for name in
                     ("actor-state.jsonl", "camera-frame-map.jsonl", "site-packet.json")}
    pixel_hashes = {name: _hash(root / name) for name in
                    ("roi-frames.jsonl", "camera-frame-map.jsonl", "approach.zip", "driver_reference.zip")}
    receipt = {"format": "beam-road-native-source-v1", "case_id": CASE["case_id"],
               "frame_count": 9, "source_hashes": source_hashes,
               "pixel_source_hashes": pixel_hashes, "camera_movies": movies,
               "physical_acceptance_claimed": False}
    (root / "native-source-receipt.json").write_text(json.dumps(receipt) + "\n")


class AnalysisTests(unittest.TestCase):
    def setUp(self):
        TEMP_ROOT.mkdir(parents=True, exist_ok=True)
        self.tmp = tempfile.TemporaryDirectory(prefix="saved-", dir=TEMP_ROOT)
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        fixture(self.root)

    def test_saved_analysis_emits_five_source_bound_requirements(self):
        report = build(self.root, expected_frames=9, diagnostic=True)
        self.assertEqual(report["case_id"], CASE["case_id"])
        self.assertEqual(set(report["measurements"]), {"beam_requirement_0", "beam_requirement_1",
                                                         "beam_requirement_2", "beam_requirement_3",
                                                         "beam_requirement_4"})
        self.assertGreater(report["measurements"]["beam_requirement_2"]["value"]["within_500ft_frame_count"], 0)
        self.assertFalse(report["legal_verdict_claimed"])

    def test_changed_movie_rejected(self):
        (self.root / "approach.mkv").write_text("tampered\n")
        with self.assertRaisesRegex(ValueError, "camera movie differs"):
            build(self.root, expected_frames=9, diagnostic=True)

    def test_changed_site_case_rejected(self):
        site = self.root / "site-packet.json"
        value = json.loads(site.read_text())
        value["case_id"] = "wrong"
        site.write_text(json.dumps(value) + "\n")
        with self.assertRaisesRegex(ValueError, "original site does not bind"):
            build(self.root, expected_frames=9, diagnostic=True)

    def test_missing_eye_pixels_rejected(self):
        (self.root / "driver_reference.zip").unlink()
        with self.assertRaisesRegex(ValueError, "Missing required source"):
            build(self.root, expected_frames=9, diagnostic=True)


if __name__ == "__main__":
    unittest.main()
