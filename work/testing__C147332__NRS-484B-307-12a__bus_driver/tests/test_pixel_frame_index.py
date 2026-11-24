"""CPU pixel-byte custody tests; synthetic frames never prove visibility."""
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))
from pixel_frame_index import index_attempt, read_exact, sha
from pixel_review_export import export, selected_frames
from pixel_review_annotations import validate as validate_annotations
from test_saved_analysis import sealed_fixture


class PixelFrameIndexTests(unittest.TestCase):
    def test_review_export_binds_current_code_in_all_selected_cases(self):
        manifest = json.loads((ROOT / "execution-manifest.json").read_text())
        for entry in manifest["cases"]:
            receipt = entry["delivery_acceptance"]["pixel_review_export"]
            self.assertEqual(receipt["script_sha256"], sha(ROOT / receipt["script"]))
            self.assertIn("--pixel-index", receipt["command"])
            self.assertFalse(receipt["pixel_visibility_reviewed"])
            human = entry["delivery_acceptance"]["pixel_review_annotations"]
            self.assertEqual(human["script_sha256"], sha(ROOT / human["script"]))
            self.assertIn("--review", human["command"])
            self.assertIn("--attempt", human["command"])
            self.assertIn("--pixel-index", human["command"])
            self.assertIn(receipt["command"].split("--output ", 1)[1],
                          human["command"])
            pixel = entry["delivery_acceptance"]["pixel_index"]
            self.assertIn(pixel["command"].split("--output ", 1)[1],
                          human["command"])
            self.assertFalse(human["reviewed"])
            self.assertFalse(human["physical_acceptance_claimed"])

    def test_source_bound_review_export_keeps_visibility_unreviewed(self):
        scratch = REPO / ".runtime-work" / "c147332-pixel-review-tests"
        scratch.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=scratch) as directory:
            base = Path(directory)
            attempt = base / "attempt"
            attempt.mkdir()
            sealed_fixture(attempt)
            index_path = base / "index.json"
            index_path.write_text(json.dumps(index_attempt(attempt, diagnostic=True)) + "\n")
            sheet = export(attempt, index_path, base / "images", diagnostic=True)
            self.assertEqual(sheet["selected_video_frames"], [0, 1, 2])
            self.assertEqual(len(sheet["samples"]), 12)
            self.assertTrue(all(sha(base / "images" / row["image"]) == row["image_sha256"]
                                for row in sheet["samples"]))
            self.assertTrue((base / "images" / sheet["samples"][0]["image"]).read_bytes().startswith(b"P6\n"))
            self.assertFalse(sheet["pixel_visibility_reviewed"])
            self.assertFalse(sheet["physical_acceptance_claimed"])
            altered = json.loads(index_path.read_text())
            altered["cameras"]["overview"]["frames"][1]["rgb24_sha256"] = "0" * 64
            index_path.write_text(json.dumps(altered) + "\n")
            with self.assertRaisesRegex(ValueError, "pixel index differs"):
                export(attempt, index_path, base / "rejected", diagnostic=True)

    def test_human_review_requires_every_source_bound_frame_and_rejects_fixture(self):
        scratch = REPO / ".runtime-work" / "c147332-pixel-review-tests"
        scratch.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=scratch) as directory:
            base = Path(directory)
            attempt = base / "attempt"
            attempt.mkdir()
            sealed_fixture(attempt)
            index_path = base / "index.json"
            index_path.write_text(json.dumps(index_attempt(attempt, diagnostic=True)) + "\n")
            export_dir = base / "images"
            sheet = export(attempt, index_path, export_dir, diagnostic=True)
            sheet_path = export_dir / "review-sheet.json"
            review_path = base / "review.json"
            review = {"case_id": sheet["case_id"], "reviewer": "synthetic protocol test",
                      "review_sheet_sha256": sha(sheet_path),
                      "observations": [{"image": row["image"],
                                        "image_sha256": row["image_sha256"],
                                        "answers": {"bus_visible": "uncertain",
                                                    "green_arrow_legible": "uncertain",
                                                    "lane_association_visible": "uncertain"},
                                        "note": "synthetic frame; no visual claim"}
                                       for row in sheet["samples"]]}
            review_path.write_text(json.dumps(review) + "\n")
            with self.assertRaisesRegex(ValueError, "original Native acquisition required"):
                validate_annotations(export_dir, review_path, attempt, index_path)
            report = validate_annotations(export_dir, review_path, attempt, index_path,
                                          diagnostic=True)
            self.assertEqual(report["reviewed_frames"], 12)
            self.assertFalse(report["all_visible"])
            self.assertFalse(report["physical_acceptance_claimed"])
            review["observations"].pop()
            review_path.write_text(json.dumps(review) + "\n")
            with self.assertRaisesRegex(ValueError, "cover every"):
                validate_annotations(export_dir, review_path, attempt, index_path,
                                     diagnostic=True)
            review["observations"].append({"image": "unlisted.ppm", "image_sha256": "0" * 64,
                                           "answers": {key: "yes" for key in
                                                       ("bus_visible", "green_arrow_legible",
                                                        "lane_association_visible")},
                                           "note": "unlisted"})
            review_path.write_text(json.dumps(review) + "\n")
            with self.assertRaisesRegex(ValueError, "identity"):
                validate_annotations(export_dir, review_path, attempt, index_path,
                                     diagnostic=True)
            sheet["samples"][0]["carla_frame"] += 1
            sheet_path.write_text(json.dumps(sheet) + "\n")
            review["review_sheet_sha256"] = sha(sheet_path)
            review_path.write_text(json.dumps(review) + "\n")
            with self.assertRaisesRegex(ValueError, "sealed original frame"):
                validate_annotations(export_dir, review_path, attempt, index_path,
                                     diagnostic=True)

    def test_review_selection_requires_three_distinct_frames(self):
        self.assertEqual(selected_frames(4), [0, 2, 3])
        with self.assertRaisesRegex(ValueError, "at least three"):
            selected_frames(2)

    def test_selected_delivery_receipts_bind_current_pixel_index_code(self):
        manifest = json.loads((ROOT / "execution-manifest.json").read_text())
        for entry in manifest["cases"]:
            receipt = entry["delivery_acceptance"]["pixel_index"]
            self.assertEqual(receipt["script_sha256"], sha(ROOT / receipt["script"]))
            self.assertIn("--attempt", receipt["command"])
            self.assertIn("--output", receipt["command"])
            self.assertFalse(receipt["pixel_visibility_reviewed"])

    def test_four_full_decodes_join_original_frame_identity(self):
        scratch = REPO / ".runtime-work" / "c147332-pixel-index-tests"
        scratch.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=scratch) as directory:
            attempt = Path(directory)
            sealed_fixture(attempt)
            report = index_attempt(attempt, diagnostic=True)
            self.assertEqual(report["decoded_original_frames"], 3)
            self.assertEqual(len(report["cameras"]), 4)
            for camera in report["cameras"].values():
                self.assertEqual([row["carla_frame"] for row in camera["frames"]], [0, 1, 2])
                self.assertTrue(all(len(row["rgb24_sha256"]) == 64 for row in camera["frames"]))
            self.assertFalse(report["pixel_visibility_reviewed"])
            self.assertFalse(report["physical_acceptance_claimed"])

    def test_unsealed_native_claim_from_fixture_rejected(self):
        scratch = REPO / ".runtime-work" / "c147332-pixel-index-tests"
        scratch.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=scratch) as directory:
            attempt = Path(directory)
            sealed_fixture(attempt)
            with self.assertRaisesRegex(ValueError, "original Native acquisition required"):
                index_attempt(attempt)

    def test_truncated_raw_frame_rejected(self):
        with self.assertRaisesRegex(ValueError, "truncated"):
            read_exact(io.BytesIO(b"short"), 7)


if __name__ == "__main__":
    unittest.main()
