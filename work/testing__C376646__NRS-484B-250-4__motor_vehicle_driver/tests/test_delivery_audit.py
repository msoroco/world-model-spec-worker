"""Exact-case source join tests for the independent C376646 auditor."""

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

FOLDER = Path(__file__).resolve().parents[1]
REPO = FOLDER.parents[1]
SPEC = importlib.util.spec_from_file_location("c376646_delivery_audit", FOLDER / "delivery_audit.py")
AUDIT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(AUDIT)


class SourceJoinTests(unittest.TestCase):
    def test_all_five_exact_sources_and_rejections(self):
        manifest = json.loads((FOLDER / "review-draft-manifest.json").read_text())
        self.assertEqual(len(manifest["cases"]), 5)
        for case in manifest["cases"]:
            with self.subTest(case=case["case_id"]):
                recipe = json.loads((REPO / case["fixture_recipe"]).read_text())
                fixture = json.loads((REPO / recipe["generator"]["source"]).read_text())
                files = fixture["files"]
                with tempfile.TemporaryDirectory() as temporary:
                    attempt = Path(temporary)
                    for name in ("video_frames.jsonl", "vehicle_signal_history.jsonl", "trace.jsonl"):
                        (attempt / name).write_text(files[name])
                    count = len(files["video_frames.jsonl"].splitlines())
                    self.assertEqual(AUDIT.validate_join(attempt, case["case_id"], count)["frames"], count)
                    with self.assertRaisesRegex(ValueError, "frame count"):
                        AUDIT.validate_join(attempt, case["case_id"], count + 1)
                    rows = [json.loads(line) for line in files["vehicle_signal_history.jsonl"].splitlines()]
                    rows[0]["other_signal_state"] = "Green"
                    (attempt / "vehicle_signal_history.jsonl").write_text(
                        "".join(json.dumps(row) + "\n" for row in rows))
                    with self.assertRaisesRegex(ValueError, "Off signal"):
                        AUDIT.validate_join(attempt, case["case_id"], count)


if __name__ == "__main__":
    unittest.main()
