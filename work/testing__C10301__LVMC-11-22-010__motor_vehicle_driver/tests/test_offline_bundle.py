import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
AID = ROOT.name


class OfflineBundleTests(unittest.TestCase):
    def test_two_exact_bundles_bind_distinct_controller_profiles(self):
        manifest = json.loads((ROOT / "execution-manifest.draft.json").read_text())
        self.assertEqual({row["case_id"] for row in manifest["cases"]},
                         {AID + "__steady_travel", AID + "__steering_variation"})
        profiles = {}
        for row in manifest["cases"]:
            construction = json.loads((ROOT / row["construction"]).read_text())
            files = {item["path"]: item["content"] for item in construction["files"]}
            config = json.loads(files["config.json"])
            scene = json.loads(files["alley-scene.json"])
            self.assertEqual(config["selected_case_id"], row["case_id"])
            self.assertEqual(config["fps"] * config["duration_s"], 900)
            self.assertEqual(len(config["cameras"]), 4)
            self.assertEqual(scene["surface_role"], "access_aisle_adjacent_to_designated_handicapped_parking")
            self.assertTrue(construction["diagnostic_only"])
            profiles[row["case_id"]] = config["profile"]
        self.assertEqual(profiles[AID + "__steady_travel"], "steady")
        self.assertEqual(profiles[AID + "__steering_variation"], "variation")

    def test_bundle_source_code_is_current(self):
        manifest = json.loads((ROOT / "execution-manifest.draft.json").read_text())
        for row in manifest["cases"]:
            construction = json.loads((ROOT / row["construction"]).read_text())
            files = {item["path"]: item["content"] for item in construction["files"]}
            for name in ("alley_geometry.py", "native_operation.py", "native_context.py",
                         "native_capture.py", "saved_delivery.py", "saved_finalizer.py",
                         "attention_measurement.py"):
                self.assertEqual(files[name], (ROOT / name).read_text())


if __name__ == "__main__":
    unittest.main()
