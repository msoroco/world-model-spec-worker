import json
from pathlib import Path
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
from build_gpu_queue import build
from comparison_dispatch import dispatch
from prove_comparison_dispatch import sources


class LinkedQueueTest(unittest.TestCase):
    def test_exact_queue_covers_selected_cases_candidates_and_comparisons(self):
        queue = build()
        plan = json.loads((HERE / "case-plan.json").read_text())
        self.assertEqual([row["case_id"] for row in queue["cases"]],
                         [row["case_id"] for row in plan["cases"]])
        self.assertEqual([row["order"] for row in queue["cases"]], list(range(1, 7)))
        self.assertEqual([row["comparison_id"] for row in queue["comparisons"]],
                         [row["comparison_id"] for row in plan["comparisons"]])
        for row in queue["cases"]:
            self.assertEqual(set(row["candidate_commands"]),
                             {"fallback1", "fallback2", "fallback3"})
            self.assertIn('"$ATTEMPT"', row["additional_source_audit_command"])

    def test_saved_dispatch_rejects_crossed_exact_case(self):
        plan = json.loads((HERE / "case-plan.json").read_text())
        first = plan["comparisons"][0]
        by_case = sources()
        attempts = [by_case[case][0] for case in reversed(first["case_ids"])]
        with self.assertRaisesRegex(ValueError, "wrong exact case"):
            dispatch(first["comparison_id"], attempts)

    def test_queue_rejects_stale_manifest_without_touching_source(self):
        original = json.loads((HERE / "execution-manifest.json").read_text())
        original["cases"][0]["construction_sha256"] = "0" * 64
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "execution-manifest.json"
            path.write_text(json.dumps(original))
            with self.assertRaisesRegex(ValueError, "Stale exact construction"):
                build(manifest_path=path)


if __name__ == "__main__":
    unittest.main()
