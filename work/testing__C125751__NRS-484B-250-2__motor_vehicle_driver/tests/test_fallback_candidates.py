import json
import sys
import unittest
from pathlib import Path

PACKAGE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE.parents[1] / "runtime/scenario_pipeline"))
from worker_exchange.candidate_constructions import validate


class FallbackCandidateTests(unittest.TestCase):
    def test_six_exact_candidates_and_distinct_risks(self):
        manifest = json.loads((PACKAGE / "diagnostic-execution-manifest.json").read_text())
        self.assertEqual(len(manifest["cases"]), 2)
        by_case = {}
        for entry in manifest["cases"]:
            self.assertEqual(validate(PACKAGE, entry, "NRS-484B-250-2", "C125751",
                                      required=True, require_alternate=True, candidate_count=4)["fallbacks"],
                             ["fallback1", "fallback2", "fallback3"])
            candidates = entry["candidates"]
            self.assertEqual(len({(c["trigger"]["source"], c["trigger"]["metric"])
                                  for c in candidates}), 3)
            self.assertEqual(len({tuple(c["changed_knobs"]) for c in candidates}), 3)
            by_case[entry["case_id"].rsplit("__", 1)[-1]] = {
                c["id"]: (c["trigger"], c["changed_knobs"]) for c in candidates}
        self.assertEqual(by_case["signal_operative"], by_case["signal_off"])


if __name__ == "__main__":
    unittest.main()
