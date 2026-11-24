"""Check exact diagnostic bundle coverage and source binding."""
import hashlib
import json
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import build_offline_draft as draft


class DraftTests(unittest.TestCase):
    def test_four_exact_constructions(self):
        manifest = json.loads((ROOT / "execution-manifest.draft.json").read_text())
        self.assertEqual(manifest["assignment_id"], draft.ASSIGNMENT)
        self.assertEqual(len(manifest["cases"]), len(draft.SUFFIXES))
        self.assertEqual({row["case_id"] for row in manifest["cases"]},
                         {draft.ASSIGNMENT + "__" + suffix for suffix in draft.SUFFIXES})
        for row in manifest["cases"]:
            path = ROOT / row["construction"]
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), row["construction_sha256"])
            construction = json.loads(path.read_text())
            self.assertFalse(construction["diagnostic_only"])
            self.assertEqual(construction["case_id"], row["case_id"])
            files = {item["path"]: item["content"] for item in construction["files"]}
            config = json.loads(files["config.json"])
            self.assertEqual(config["selected_case_id"], row["case_id"])
            self.assertEqual(config["scenario_parameters"], next(
                item["scenario_parameters"] for item in json.loads(files["case-plan.json"])["cases"]
                if item["case_id"] == row["case_id"]))
            self.assertEqual(config["frame_count"], 900)
            for name in draft.SOURCES:
                self.assertEqual(hashlib.sha256(files[name].encode()).hexdigest(),
                                 config["code_sha256"][name])


if __name__ == "__main__":
    unittest.main()
