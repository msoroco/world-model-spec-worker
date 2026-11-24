import hashlib
import json
import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from construction import POLICIES
from saved_left_turn import ASSIGNMENT_ID


class Bundles(unittest.TestCase):
    def test_all_exact_sources_current_and_distinct(self):
        manifest = json.loads((ROOT / "bundle-checkpoint-manifest.json").read_text())
        self.assertFalse(manifest["delivery_ready"])
        self.assertEqual({entry["case_id"] for entry in manifest["cases"]},
                         {ASSIGNMENT_ID + "__" + suffix for suffix in POLICIES})
        hashes = set()
        for entry in manifest["cases"]:
            path = ROOT / entry["construction"]
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), entry["construction_sha256"])
            hashes.add(entry["construction_sha256"])
            bundle = json.loads(path.read_text())
            self.assertEqual(bundle["case_id"], entry["case_id"])
            for source in bundle["files"]:
                if "source" in source:
                    original = (ROOT / pathlib.Path(source["source"]).name).read_text()
                    if entry["case_id"].endswith(("__reciprocal_yield", "__reciprocal_no_yield")) and source["path"] == "runner.py":
                        self.assertIn("from reciprocal_entrypoint import run_native", source["content"])
                        self.assertIn("result = run_native(", source["content"])
                        self.assertNotIn("Native CARLA adapter and world lifecycle binding still required", source["content"])
                    elif entry["case_id"].endswith(("__reciprocal_yield", "__reciprocal_no_yield")) and source["path"] == "analysis.py":
                        self.assertEqual(source["content"], original.replace(
                            "from requirement_finalizer import finalize\n",
                            "from reciprocal_finalization import finalize_reciprocal as finalize\n"))
                    else:
                        self.assertEqual(original, source["content"])
            self.assertIn("delivery_audit.py", {f["path"] for f in bundle["files"]})
        self.assertEqual(len(hashes), len(POLICIES))


if __name__ == "__main__":
    unittest.main()
