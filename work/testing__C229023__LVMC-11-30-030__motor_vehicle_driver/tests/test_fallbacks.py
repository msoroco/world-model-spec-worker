import json
import os
from pathlib import Path
import sys
import unittest

HERE = Path(__file__).resolve().parents[1]
if not Path(os.environ.get("SCENARIO_PIPELINE_OUTPUT_ROOT", "/missing")).resolve().is_relative_to(HERE.parents[1] / ".runtime-work"):
    raise RuntimeError("export a .runtime-work output root before pinned imports")
sys.path.insert(0, str(HERE.parents[1] / "runtime"))
from scenario_pipeline.worker_exchange.candidate_constructions import validate


class ExactFallbackTests(unittest.TestCase):
    def test_pinned_candidate_invariants_and_source_bound_offline_receipts(self):
        manifest = json.loads((HERE / "execution-manifest.json").read_text())
        self.assertEqual(len(manifest["cases"]), 6)
        for entry in manifest["cases"]:
            self.assertEqual(validate(HERE, entry, "LVMC-11-30-030", "C229023", required=False)["fallbacks"], ["fallback1"])
            candidate = entry["candidates"][0]
            self.assertEqual(candidate["offline"]["exit_code"], 0)
            self.assertEqual(candidate["offline"]["construction_sha256"], candidate["construction_sha256"])
            self.assertEqual(candidate["compatibility"]["status"], "pending source-shaped positive and missing-source negative")


if __name__ == "__main__":
    unittest.main()
