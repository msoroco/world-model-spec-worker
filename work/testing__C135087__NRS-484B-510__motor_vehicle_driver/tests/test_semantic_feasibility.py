import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from semantic_feasibility import describe_run, derive


class SemanticFeasibilityTests(unittest.TestCase):
    def test_observed_relations_do_not_become_legal_cutoffs(self):
        rows = [{"time_s": i, "passenger_exchange_active": 8 <= i <= 15,
                 "entrant_parking_task_active": True,
                 "entrant_speed_mps": 1 if i >= 10 else 0,
                 "entrant_waiting": i == 14, "entrant_access_blocked": i == 14,
                 "subject_speed_mps": 0} for i in range(25)]
        result = describe_run(rows)
        self.assertEqual(result["relation"], "during_exchange")
        self.assertEqual(result["legal_interference"], "unresolved_judgment")
        for row in rows[10:16]:
            row["entrant_speed_mps"] = 0
        for row in rows[16:]:
            row["entrant_speed_mps"] = 1
        self.assertEqual(describe_run(rows)["relation"], "after_exchange")

    def test_missing_original_sources_rejected(self):
        with self.assertRaisesRegex(ValueError, "sealed original Native attempt missing"):
            derive({"case-a": Path(".runtime-work/no-original-a"),
                    "case-b": Path(".runtime-work/no-original-b"),
                    "case-c": Path(".runtime-work/no-original-c")})


if __name__ == "__main__":
    unittest.main()
