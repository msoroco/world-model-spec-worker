"""Positive and controlled negative checks over the selected textual sources."""
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from audit_opposite_comparison import compare

SOURCE = ROOT / "selected-source"
FILES = ("road.xodr", "video_frames.jsonl", "entrance-context.json",
         "acquisition-provenance.json",
         "native-vehicle.jsonl")
CAMERAS = ("overview", "approach", "reference_corner", "driver_reference")


class OppositeComparisonTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.far = Path(self.temp.name) / "far"
        self.near = Path(self.temp.name) / "near"
        for suffix, target in (("opposite_far", self.far),
                               ("opposite_near", self.near)):
            target.mkdir()
            for name in FILES:
                shutil.copyfile(SOURCE / suffix / name, target / name)
            for name in CAMERAS:
                (target / (name + ".mkv")).write_bytes(b"fixture camera placeholder")

    def alter_row(self, folder, index, key, value):
        path = folder / "native-vehicle.jsonl"
        rows = [json.loads(line) for line in path.read_text().splitlines()]
        rows[index][key] = value
        path.write_text("\n".join(json.dumps(row) for row in rows) + "\n")

    def test_positive_raw_bracket_with_uncertainty(self):
        result = compare(self.far, self.near)
        self.assertEqual((result["far_raw_body_edge_gap_m"],
                          result["near_raw_body_edge_gap_m"]), (30, 5))
        self.assertFalse(result["statutory_reference_method_adopted"])
        self.assertFalse(result["physical_or_legal_result_claimed"])

    def test_missing_camera_rejected(self):
        (self.far / "overview.mkv").unlink()
        with self.assertRaisesRegex(ValueError, "Missing original camera"):
            compare(self.far, self.near)

    def test_wrong_side_rejected(self):
        self.alter_row(self.near, 500, "center_xy_m", [-10, -2])
        with self.assertRaisesRegex(ValueError, "opposite side"):
            compare(self.far, self.near)

    def test_changed_fixed_context_rejected(self):
        path = self.near / "entrance-context.json"
        context = json.loads(path.read_text())
        context["exception_context"] = "traffic_conflict"
        path.write_text(json.dumps(context) + "\n")
        with self.assertRaisesRegex(ValueError, "Fixed road, timing or source context"):
            compare(self.far, self.near)

    def test_actor_swap_rejected(self):
        self.alter_row(self.near, 500, "actor_id", 9001)
        with self.assertRaisesRegex(ValueError, "Fixed actor or timing"):
            compare(self.far, self.near)

    def test_missing_bracket_rejected(self):
        path = self.far / "native-vehicle.jsonl"
        rows = [json.loads(line) for line in path.read_text().splitlines()]
        for row in rows[300:]:
            row["body_xy_m"] = [[-12, 1], [-8, 1], [-8, 3], [-12, 3]]
        path.write_text("\n".join(json.dumps(row) for row in rows) + "\n")
        with self.assertRaisesRegex(ValueError, "bracket 75 feet"):
            compare(self.far, self.near)

    def test_forged_original_authority_rejected(self):
        for folder in (self.far, self.near):
            path = folder / "entrance-context.json"
            context = json.loads(path.read_text())
            context["source_kind"] = "original_native"
            path.write_text(json.dumps(context) + "\n")
            motion = folder / "native-vehicle.jsonl"
            rows = [json.loads(line) for line in motion.read_text().splitlines()]
            for row in rows:
                row["source_kind"] = "original_native"
            motion.write_text("\n".join(json.dumps(row) for row in rows) + "\n")
        with self.assertRaisesRegex(ValueError, "Original authority manifest"):
            compare(self.far, self.near)


if __name__ == "__main__":
    unittest.main()
