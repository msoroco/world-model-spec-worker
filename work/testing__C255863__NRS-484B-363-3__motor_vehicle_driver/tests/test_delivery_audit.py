"""Diagnostic packet tests for the independent delivery source inventory."""

import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import delivery_audit
from school_scene_construction import ASSIGNMENT


class DeliveryAuditTests(unittest.TestCase):
    def packet(self, root):
        plan = json.loads((Path(__file__).resolve().parents[1] / "case-plan.json").read_text())
        index = {}
        for case in plan["cases"]:
            case_id = case["case_id"]
            files = {}
            for name in ("context", "trace", "receipt", "camera_manifest",
                         "measurement", "comparison_packet"):
                path = root / (case_id.split("__")[-1] + "-" + name + ".json")
                value = {"statutory_disposition": "unresolved_pending_source_review"} if name == "measurement" else {"diagnostic_source": name}
                path.write_text(json.dumps(value) + "\n")
                files[name] = {"path": path.name,
                               "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
            index[case_id] = files
        return index

    def test_six_cases_and_five_comparisons(self):
        with tempfile.TemporaryDirectory(dir=os.environ["SCENARIO_PIPELINE_OUTPUT_ROOT"]) as folder:
            root = Path(folder)
            packet = self.packet(root)
            index = root / "index.json"
            index.write_text(json.dumps({"assignment_id": ASSIGNMENT,
                                         "source_kind": "original_native_delivery",
                                         "cases": packet}) + "\n")
            with patch.object(delivery_audit, "finalize", return_value={"statutory_disposition": "unresolved_pending_source_review"}), patch.object(delivery_audit, "compare", return_value={"fixed_geometry_and_states_checked": True}):
                result = delivery_audit.audit(index)
            self.assertEqual(result["case_count"], 6)
            self.assertEqual(result["comparison_count"], 5)
            changed = root / next(iter(packet.values()))["context"]["path"]
            changed.write_text("changed original bytes\n")
            with self.assertRaisesRegex(ValueError, "original delivery source changed"):
                delivery_audit.audit(index)
