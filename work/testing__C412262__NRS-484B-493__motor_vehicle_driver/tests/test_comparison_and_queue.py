import hashlib
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from build_queue_proposal import build
from comparison_audit import audit
from source_audit import audit as audit_sources
from street_scene_construction import ASSIGNMENT, load_case


class ComparisonQueueTests(unittest.TestCase):
    def sources(self, directory, suffix):
        case = load_case(ASSIGNMENT + "__" + suffix)
        root = Path(directory) / suffix
        root.mkdir()
        context = {"case_id": case["case_id"], "one_way_status": "one_way",
                   "notice_state": case["notice_request"],
                   "permitted_direction_centerline_xy_m": [[0, 0], [20, 0]],
                   "camera_plan_sha256": "a" * 64, "duration_frames": 900}
        for name in ("street_legal_status_source", "street_boundary_source",
                     "public_access_source", "city_limits_source", "one_way_order_source",
                     "permitted_direction_source", "centerline_source", "notice_erection_source",
                     "notice_authority_source", "notice_exact_content_source",
                     "notice_conformity_source", "notice_extent_source", "person_identity_source",
                     "vehicle_identity_source", "halt_purpose_source", "service_activity_source",
                     "occupancy_source"):
            context[name] = "original-ref:" + name
        context_path = root / "context.json"
        context_path.write_text(json.dumps(context) + "\n")
        trace = root / "trace.jsonl"
        trace.write_text("".join(json.dumps({"frame": i, "time_s": i / 20,
                                              "vehicle_speed_mps": 0,
                                              "vehicle_center_xy_m": [10, 3],
                                              "vehicle_body_polygon_xy_m": [[9, 2], [11, 2],
                                                                            [11, 4], [9, 4]]}) + "\n"
                                 for i in range(900)))
        receipt = root / "receipt.json"
        receipt.write_text(json.dumps({"assignment_id": ASSIGNMENT,
                                       "case_id": case["case_id"],
                                       "source_kind": "original_native_capture",
                                       "diagnostic_fixture": False, "fps": 20,
                                       "frame_count": 900,
                                       "context_sha256": hashlib.sha256(context_path.read_bytes()).hexdigest(),
                                       "trace_sha256": hashlib.sha256(trace.read_bytes()).hexdigest()}) + "\n")
        return {"case_id": case["case_id"], "context": str(context_path),
                "trace": str(trace), "receipt": str(receipt)}

    def test_standing_comparison_and_changed_protocol(self):
        with tempfile.TemporaryDirectory(dir=os.environ["TMPDIR"]) as directory:
            left = self.sources(directory, "park_left_notice")
            right = self.sources(directory, "stand_left_notice")
            self.assertTrue(audit("stand_left_notice", left, right)["fixed_sources_and_protocol_checked"])
            context = Path(right["context"])
            value = json.loads(context.read_text())
            value["camera_plan_sha256"] = "b" * 64
            context.write_text(json.dumps(value) + "\n")
            receipt = Path(right["receipt"])
            rec = json.loads(receipt.read_text())
            rec["context_sha256"] = hashlib.sha256(context.read_bytes()).hexdigest()
            receipt.write_text(json.dumps(rec) + "\n")
            with self.assertRaisesRegex(ValueError, "camera_plan_sha256"):
                audit("stand_left_notice", left, right)

    def test_queue_and_source_inventory(self):
        repo = Path(__file__).resolve().parents[3]
        self.assertEqual(audit_sources(repo)["accepted_metadata_count"], 0)
        self.assertEqual(len(audit_sources(repo)["missing_source_classes"]), 5)
        proposal = build()
        self.assertEqual(len(proposal["cases"]), 9)
        self.assertEqual(len(proposal["comparison_audit_commands"]), 8)
        self.assertEqual([row["order"] for row in proposal["cases"]], list(range(1, 10)))
        for row in proposal["cases"]:
            self.assertIn('--root "$LOCAL_ROOT" prepare-delivery', row["prepare_command"])
            self.assertIn('--root "$LOCAL_ROOT" execute-delivery', row["execute_command"])
            self.assertIn('--root "$LOCAL_ROOT" accept-delivery', row["accept_command"])
            self.assertIn('--review-archive /external/archive', row["accept_command"])


if __name__ == "__main__":
    unittest.main()
