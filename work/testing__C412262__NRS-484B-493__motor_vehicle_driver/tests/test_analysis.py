"""Bounded synthetic saved-input fixtures test measurement and negative source."""

import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

PACKAGE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE))
from analysis import measure, required
from street_scene_construction import ASSIGNMENT, load_case

CASE = json.loads((PACKAGE / "config.json").read_text())["selected_case_id"]


def write(path, value):
    path.write_text(json.dumps(value, sort_keys=True) + "\n")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class AnalysisTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=os.environ["TMPDIR"])
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        for name in ("config.json", "construction.json"):
            shutil.copyfile(PACKAGE / name, self.root / name)
        context = {"case_id": CASE, "one_way_status": "one_way",
                   "notice_state": "erected_applicable",
                   "permitted_direction_centerline_xy_m": [[0, 0], [20, 0]]}
        case = load_case(CASE)
        context.update({key: case[key] for key in ("street_direction_request",
                                                    "vehicle_side_request", "activity_request",
                                                    "notice_request")})
        write(self.root / "context.json", context)
        with (self.root / "original-trace.jsonl").open("w") as stream:
            for i in range(9):
                stream.write(json.dumps({"frame": i, "time_s": i / 20,
                                         "vehicle_center_xy_m": [10, 3],
                                         "vehicle_body_polygon_xy_m": [[9, 2], [11, 2],
                                                                       [11, 4], [9, 4]]}) + "\n")
        write(self.root / "cameras.json", {"synthetic_fixture": True})
        write(self.root / "fixture-provenance.json", {"diagnostic_fixture": True})
        write(self.root / "receipt.json", {
            "source_kind": "synthetic_diagnostic_fixture", "assignment_id": ASSIGNMENT,
            "case_id": CASE, "context_sha256": sha(self.root / "context.json"),
            "trace_sha256": sha(self.root / "original-trace.jsonl"),
            "camera_manifest_sha256": sha(self.root / "cameras.json")})

    def test_diagnostic_measurement_has_no_legal_claim(self):
        _, values, hashes, fixture, _ = measure(self.root)
        self.assertTrue(fixture)
        self.assertEqual(values["original_frame_count"], 9)
        self.assertEqual(values["first_body_signed_left_offset_range_m"], [2, 4])
        self.assertEqual(values["statutory_side_judgment"], "unresolved")
        self.assertEqual(hashes["context.json"], sha(self.root / "context.json"))

    def test_missing_case_source_rejected(self):
        (self.root / "context.json").unlink()
        with self.assertRaisesRegex(ValueError, "Missing required source: context.json"):
            measure(self.root)


if __name__ == "__main__":
    unittest.main()
