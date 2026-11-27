"""Source-gate tests for statutory activity and exception variants."""
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "native"))
import branch_context


class BranchSourceGateTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="c135702-branch-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.case = ROOT.name + "__selected_branch_source_probe"
        self.context = {"case_id": self.case, "source_kind": "reviewed_branch_context",
                        "exception_sources": {}}
        self.context["activity_source"] = self.write_record(
            "operator_activity", {"requested_activity": "stand"})
        for name in sorted(branch_context.EXCEPTIONS):
            fields = {"requested_exception": name, "event_window": "source 0-30 s",
                      "scene_scope": "surveyed obstruction highway"}
            if name in {"police_direction", "traffic_device"}:
                fields["original_instruction"] = "source instruction retained for later review"
            elif name == "law_direction":
                fields["law_citation"] = "source citation retained for later review"
            else:
                fields["traffic_source_refs"] = ["original traffic body and frame records"]
            self.context["exception_sources"][name] = self.write_record(name, fields)
        self.path = self.root / "context.json"
        self.save()

    def write_record(self, kind, fields):
        path = self.root / (kind + ".json")
        path.write_text(json.dumps({"source_kind": kind,
                                    "original_record_id": "fixture-" + kind, **fields}) + "\n")
        return {"kind": kind, "provenance": "reviewed_original_source",
                "path": path.name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}

    def save(self):
        self.path.write_text(json.dumps(self.context) + "\n")

    def test_each_exception_source_gate_preserves_judgment(self):
        for name in sorted(branch_context.EXCEPTIONS):
            with self.subTest(name=name):
                value = branch_context.validate(self.root, self.path, self.case, "stand", name)
                self.assertIsNone(value["exception_applies"])
                self.assertFalse(value["activity_observed"])
                self.assertFalse(value["legal_acceptance_claimed"])

    def test_activity_mismatch_rejected(self):
        with self.assertRaisesRegex(ValueError, "activity source"):
            branch_context.validate(self.root, self.path, self.case, "stop", None)

    def test_missing_separate_authority_rejected(self):
        del self.context["exception_sources"]["traffic_device"]
        self.save()
        with self.assertRaisesRegex(ValueError, "Four separate"):
            branch_context.validate(self.root, self.path, self.case, "stand", None)

    def test_changed_original_source_rejected(self):
        (self.root / "police_direction.json").write_text("{}\n")
        with self.assertRaisesRegex(ValueError, "missing or changed"):
            branch_context.validate(self.root, self.path, self.case, "stand", None)

    def test_missing_original_instruction_rejected(self):
        self.context["exception_sources"]["police_direction"] = self.write_record(
            "police_direction", {"requested_exception": "police_direction",
                                 "event_window": "source 0-30 s",
                                 "scene_scope": "surveyed obstruction highway"})
        self.save()
        with self.assertRaisesRegex(ValueError, "original instruction"):
            branch_context.validate(self.root, self.path, self.case, "stand", "police_direction")

    def test_case_mismatch_rejected(self):
        with self.assertRaisesRegex(ValueError, "case-specific"):
            branch_context.validate(self.root, self.path, self.case + "x", "stand", None)


if __name__ == "__main__":
    unittest.main()
