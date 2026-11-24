"""Exact per-case positive and missing-context diagnostic source tests."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from analysis import finalize


class DiagnosticSources(unittest.TestCase):
    def test_all_five_exact_cases_and_missing_context(self):
        manifest = json.loads((ROOT / "execution-manifest.json").read_text())
        for entry in manifest["cases"]:
            case_id = entry["case_id"]
            short = case_id.removeprefix(manifest["assignment_id"] + "__")
            with self.subTest(short=short), tempfile.TemporaryDirectory() as directory:
                target = Path(directory)
                spec = json.loads((ROOT / ("diagnostic-" + short + ".json")).read_text())
                for relative in ("frame-map.json", "bicycle-motion.json", "context.json",
                                 "inventory.json", "fixture-provenance.json"):
                    (target / relative).write_text(spec["files"][relative])
                construction = json.loads((ROOT / entry["construction"]).read_text())
                config = next(row["content"] for row in construction["files"] if row["path"] == "config.json")
                (target / "config.json").write_text(config)
                report = finalize(target)
                self.assertEqual(report["case_id"], case_id)
                self.assertEqual(len(report["measurements"]["actual_bicycle_speed_history"]["value"]), 9)
                self.assertTrue(report["diagnostic_fixture"])
                self.assertEqual(report["legal_prudence"], "unresolved")
                (target / "context.json").unlink()
                with self.assertRaisesRegex(ValueError, "Missing required source: context.json"):
                    finalize(target)


if __name__ == "__main__":
    unittest.main()
