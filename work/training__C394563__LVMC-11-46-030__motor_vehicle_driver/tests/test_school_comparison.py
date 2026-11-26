"""Independent school-warning comparison proof on source-shaped CPU fixtures."""

import json
import os
from pathlib import Path
import sys
import tempfile
import unittest


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from audit_school_comparison import CASES, audit
from prove_school_warning import context, trace


class ComparisonAudit(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(dir=os.environ["TMPDIR"])
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.inputs = {}
        for index, (case_id, distance) in enumerate(zip(CASES, (55, 40))):
            sample_context = context()
            sample_context["case_id"] = case_id
            context_path = self.root / f"context-{index}.json"
            trace_path = self.root / f"trace-{index}.jsonl"
            context_path.write_text(json.dumps(sample_context) + "\n")
            trace_path.write_text("\n".join(json.dumps(row) for row in trace(distance)) + "\n")
            self.inputs[case_id] = {"context": context_path, "trace": trace_path}

    def _change_context(self, case_id, change):
        path = self.inputs[case_id]["context"]
        payload = json.loads(path.read_text())
        change(payload)
        path.write_text(json.dumps(payload) + "\n")

    def _change_trace(self, case_id, change):
        path = self.inputs[case_id]["trace"]
        payload = [json.loads(line) for line in path.read_text().splitlines()]
        change(payload)
        path.write_text("\n".join(json.dumps(row) for row in payload) + "\n")

    def test_positive_exact_distance_comparison(self):
        result = audit(self.inputs)
        self.assertEqual(result["case_ids"], list(CASES))
        self.assertAlmostEqual(result["measured_stop_centre_ft"][CASES[0]], 55)
        self.assertAlmostEqual(result["measured_stop_centre_ft"][CASES[1]], 40)
        self.assertIsNone(result["legal_outcome"])

    def test_missing_case_rejected(self):
        with self.assertRaisesRegex(ValueError, "cases missing"):
            audit({CASES[0]: self.inputs[CASES[0]]})

    def test_changed_lane_source_rejected(self):
        self._change_context(CASES[1], lambda item: item.update(
            school_lane_geometry_sha256="f" * 64))
        with self.assertRaisesRegex(ValueError, "school_lane_geometry_sha256"):
            audit(self.inputs)

    def test_changed_warning_timeline_rejected(self):
        self._change_trace(CASES[1], lambda rows: rows[220].update(warning_active=False))
        with self.assertRaisesRegex(ValueError, "warning_active"):
            audit(self.inputs)

    def test_missing_camera_rejected(self):
        self._change_trace(CASES[1], lambda rows: rows[220]["source_cameras"].pop("approach"))
        with self.assertRaisesRegex(ValueError, "Four source camera"):
            audit(self.inputs)

    def test_changed_release_policy_rejected(self):
        self._change_trace(CASES[1], lambda rows: rows[250].update(release_event="signal_removed"))
        with self.assertRaisesRegex(ValueError, "release_event"):
            audit(self.inputs)

    def test_undemonstrated_distance_rejected(self):
        self._change_trace(CASES[1], lambda rows: [row.update(
            vehicle_center_x_m=row["vehicle_center_x_m"] + 4)
            for row in rows])
        with self.assertRaisesRegex(ValueError, "Requested and measured"):
            audit(self.inputs)


if __name__ == "__main__":
    unittest.main()
