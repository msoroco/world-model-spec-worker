import json
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))

from build_source_gated_manifest import build as select_production
from build_statutory_matrix import build as build_matrix


class StatutoryMatrixTests(unittest.TestCase):
    def test_full_frozen_inventory_and_exception_cells(self):
        result = build_matrix()
        matrix = json.loads((HERE / "statutory-matrix.draft.json").read_text())
        self.assertEqual(result["accepted_case_ids"], 11)
        self.assertEqual(result["branches"], 7)
        self.assertEqual({item["candidate_cell_id"] for item in
                          matrix["additional_binding_candidates"]},
                         {"C158170", "C158190", "C158196"})
        accepted = set(matrix["accepted_recordings"])
        self.assertEqual({case for branch in matrix["branches"]
                          for case in branch["case_ids"]}, accepted)
        self.assertTrue(all(row["status"] == "source_and_binding_review_pending"
                            for row in matrix["additional_binding_candidates"]))

    def test_production_selection_requires_full_exact_branch_assembly(self):
        with tempfile.TemporaryDirectory() as scratch:
            source = Path(scratch) / "assembly.json"
            source.write_text(json.dumps({"assignment_id": HERE.name, "cases": {}}))
            with self.assertRaisesRegex(ValueError, "every matrix case"):
                select_production(source)
        self.assertFalse((HERE / "execution-manifest.json").exists())


if __name__ == "__main__":
    unittest.main()
