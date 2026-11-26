"""Exact synthetic source joins for all driveway branches; no physical claims."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from driveway_measurements import measure


class DiagnosticSourceTest(unittest.TestCase):
    def test_all_exact_branch_sources_are_sealed_and_measured(self):
        plan = json.loads((ROOT / "case-plan.json").read_text())
        scratch = ROOT.parents[1] / ".runtime-work" / "c229404-source-tests"
        scratch.mkdir(parents=True, exist_ok=True)
        for case in plan["cases"]:
            slug = case["case_id"].removeprefix(ROOT.name + "__")
            with self.subTest(case=slug), tempfile.TemporaryDirectory(dir=scratch) as temporary:
                folder = ROOT / "diagnostics" / slug
                recipe = json.loads((folder / "fixture-recipe.json").read_text())
                spec_path = folder / "diagnostic.json"
                self.assertEqual(recipe["generator"]["sha256"],
                                 hashlib.sha256(spec_path.read_bytes()).hexdigest())
                source = json.loads(spec_path.read_text())["files"]
                target = Path(temporary)
                for name in ("original-attempt/reviewed-context.json",
                             "original-attempt/body-control-trace.jsonl",
                             "original-attempt/capture-receipt.json", "road.xodr"):
                    path = target / name
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_text(source[name])
                receipt = json.loads((target / "original-attempt/capture-receipt.json").read_text())
                self.assertTrue(receipt["diagnostic_fixture"])
                self.assertFalse(receipt["physical_acceptance_claimed"])
                observed = measure(case["case_id"],
                                   target / "original-attempt/reviewed-context.json",
                                   target / "original-attempt/body-control-trace.jsonl",
                                   target / "original-attempt/capture-receipt.json",
                                   target / "road.xodr", diagnostic=True)
                self.assertEqual(observed["activity_window"]["state"], case["activity"])
                self.assertEqual(observed["activity_window"]["frame_count"], 9)
                self.assertEqual(observed["physical_acceptance"], "unverified")
                distance = observed["minimum_observed_full_footprint_to_mouth_m"]
                if case["position_target"] == "front":
                    self.assertEqual(distance, 0)
                elif case["position_target"] == "within_5ft":
                    self.assertTrue(0 < distance < 1.524)
                else:
                    self.assertGreater(distance, 1.524)


if __name__ == "__main__":
    unittest.main()
