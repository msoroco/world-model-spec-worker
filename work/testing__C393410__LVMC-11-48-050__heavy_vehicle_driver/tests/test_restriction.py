"""Original-source gates and exact numeric/time source measurements."""
from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from restriction_measure import load_review, measure
from runner import check

ROOT = Path(__file__).resolve().parents[1]
SCRATCH = ROOT.parents[1] / ".runtime-work/c393410-050-tests"


class RestrictionSourceTests(unittest.TestCase):
    def test_all_selected_controls_have_exact_source_targets(self):
        plan = json.loads((ROOT / "case-plan.json").read_text())
        SCRATCH.mkdir(parents=True, exist_ok=True)
        self.assertEqual(len(plan["cases"]), 13)
        for case in plan["cases"]:
            short = case["case_id"].split("__")[-1]
            folder = ROOT / "cases" / short
            diagnostic = json.loads((folder / "diagnostic.json").read_text())
            files = diagnostic["files"]
            with tempfile.TemporaryDirectory(dir=SCRATCH) as temporary:
                tmp = Path(temporary)
                for name, selected in (("config.json", "config.json"),
                                       ("case-spec.json", "case-spec.json"),
                                       ("controller.json", "controller-primary.json")):
                    (tmp / name).write_bytes((folder / selected).read_bytes())
                self.assertEqual(check(tmp)["case_id"], case["case_id"])
                (tmp / "synthetic.txt").write_text(files["reviewed-sources/synthetic.txt"])
                review = tmp / "review.json"
                review.write_text(files["reviewed-night-truck.json"])
                source = tmp / "operation.json"
                source.write_text(files["original-night-truck-observations.json"])
                packet = load_review(review, tmp, case["case_id"], diagnostic=True)
                observed = measure(source)
                self.assertEqual(packet["vehicle"]["unladen_weight_lb"], case["target_unladen_lb"])
                self.assertEqual(observed["actual_unladen_weight_lb"], case["target_unladen_lb"])
                self.assertEqual(observed["local_civil_start_hhmm"], case["target_local_time"])
                self.assertEqual(observed["permit_review_status"], case["target_permit_status"])
                self.assertEqual(observed["district_reviewed_as"], case["target_district"])
                self.assertEqual(observed["traveled_street_designation"], case["target_street_class"])
                self.assertEqual(observed["legal_time_endpoint_judgment"], "unresolved")

    def test_original_provenance_and_changed_source_rejected(self):
        SCRATCH.mkdir(parents=True, exist_ok=True)
        folder = ROOT / "cases/night_nonroute_no_permit"
        files = json.loads((folder / "diagnostic.json").read_text())["files"]
        with tempfile.TemporaryDirectory(dir=SCRATCH) as temporary:
            tmp = Path(temporary)
            source = tmp / "synthetic.txt"
            source.write_text(files["reviewed-sources/synthetic.txt"])
            review = tmp / "review.json"
            review.write_text(files["reviewed-night-truck.json"])
            case_id = ROOT.name + "__night_nonroute_no_permit"
            with self.assertRaisesRegex(ValueError, "Diagnostic night truck packet"):
                load_review(review, tmp, case_id, diagnostic=False)
            source.write_text("changed\n")
            with self.assertRaisesRegex(ValueError, "source missing or changed"):
                load_review(review, tmp, case_id, diagnostic=True)

    def test_weight_boundary_is_strictly_greater(self):
        expected = {"weight_below_8000": False, "weight_at_8000": False,
                    "night_nonroute_no_permit": True}
        SCRATCH.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=SCRATCH) as temporary:
            source = Path(temporary) / "observations.json"
            for short, above in expected.items():
                files = json.loads((ROOT / "cases" / short / "diagnostic.json").read_text())["files"]
                source.write_text(files["original-night-truck-observations.json"])
                self.assertEqual(measure(source)["weight_strictly_exceeds_8000"], above)


if __name__ == "__main__":
    unittest.main()
