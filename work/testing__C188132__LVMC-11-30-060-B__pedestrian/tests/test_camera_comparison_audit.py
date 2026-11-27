import json
import tempfile
import unittest
from pathlib import Path

from camera_comparison_audit import ROOT, check_selected_cameras, selected_plan, sha


def attempt(root, variant, candidate):
    manifest_path = ROOT / "execution-manifest.json"
    manifest = json.loads(manifest_path.read_text())
    case_id = ROOT.name + "__" + variant
    row = next(item for item in manifest["cases"] if item["case_id"] == case_id)
    selection = ({"id": "primary", "construction": row["construction"],
                  "construction_sha256": row["construction_sha256"]}
                 if candidate == "primary" else
                 next(item for item in row["candidates"] if item["id"] == candidate))
    construction = json.loads((ROOT / selection["construction"]).read_text())
    root.mkdir()
    (root / "construction.json").write_text(json.dumps(construction))
    for item in construction["files"]:
        if item["path"] in ("native_capture.py", "scene.json"):
            (root / item["path"]).write_text(item["content"])
    (root / "candidate-selection.json").write_text(json.dumps({
        "format": "worker-candidate-selection", "case_id": case_id,
        "candidate_id": candidate,
        "construction_sha256": selection["construction_sha256"],
        "manifest_sha256": sha(manifest_path)}))
    return root


class CameraComparisonTests(unittest.TestCase):
    def test_matching_selected_primary_and_fallback_plans(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            first = attempt(root / "first", "yield_before_vehicle", "primary")
            second = attempt(root / "second", "enter_ahead_of_vehicle", "primary")
            binding = check_selected_cameras(first, second, "entry_timing")
            self.assertEqual(len(binding["camera_plan_sha256"]), 64)
            self.assertEqual(selected_plan(first, ROOT.name + "__yield_before_vehicle"),
                             selected_plan(second, ROOT.name + "__enter_ahead_of_vehicle"))
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            first = attempt(root / "first", "enter_ahead_of_vehicle", "fallback1")
            second = attempt(root / "second", "designated_prohibition", "fallback1")
            self.assertEqual(check_selected_cameras(first, second, "designated_exception")
                             ["case_ids"][0], ROOT.name + "__enter_ahead_of_vehicle")

    def test_rejects_mixed_camera_selection(self):
        for comparison, variants in (("entry_timing", ("yield_before_vehicle",
                                                       "enter_ahead_of_vehicle")),
                                     ("designated_exception", ("enter_ahead_of_vehicle",
                                                               "designated_prohibition"))):
            with self.subTest(comparison=comparison), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                first = attempt(root / "first", variants[0], "primary")
                second = attempt(root / "second", variants[1], "fallback1")
                with self.assertRaisesRegex(ValueError, "fixed camera positions"):
                    check_selected_cameras(first, second, comparison)

    def test_rejects_stale_selection_and_original_camera_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            first = attempt(root / "first", "yield_before_vehicle", "primary")
            second = attempt(root / "second", "enter_ahead_of_vehicle", "primary")
            source = second / "native_capture.py"
            source.write_text(source.read_text().replace("(-18.0, -15.0, 22.0)",
                                                         "(-18.0, -14.0, 22.0)"))
            with self.assertRaisesRegex(ValueError, "original camera source or scene differs"):
                check_selected_cameras(first, second, "entry_timing")
            source.write_text(next(item["content"] for item in json.loads(
                (second / "construction.json").read_text())["files"]
                if item["path"] == "native_capture.py"))
            receipt = second / "candidate-selection.json"
            selection = json.loads(receipt.read_text())
            selection["construction_sha256"] = "0" * 64
            receipt.write_text(json.dumps(selection))
            with self.assertRaisesRegex(ValueError, "selected original camera construction differs"):
                check_selected_cameras(first, second, "entry_timing")


if __name__ == "__main__":
    unittest.main()
