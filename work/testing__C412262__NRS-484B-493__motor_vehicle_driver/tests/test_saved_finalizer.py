"""Synthetic protocol fixtures exercise only saved-source integrity checks."""

import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from saved_finalizer import finalize
from street_scene_construction import ASSIGNMENT

CASE = ASSIGNMENT + "__park_left_notice"


def write(path, value):
    path.write_text(json.dumps(value, sort_keys=True) + "\n")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class FinalizerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=os.environ["TMPDIR"])
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.context = root / "context.json"
        self.trace = root / "trace.jsonl"
        self.receipt = root / "receipt.json"
        self.cameras = root / "cameras.json"
        context = {"case_id": CASE, "one_way_status": "one_way",
                   "notice_state": "erected_applicable",
                   "permitted_direction_centerline_xy_m": [[0, 0], [20, 0]],
                   "street_direction_request": "one_way", "vehicle_side_request": "left",
                   "activity_request": "park", "notice_request": "erected_applicable"}
        for key in ("street_legal_status_source", "street_boundary_source",
                    "public_access_source", "city_limits_source", "one_way_order_source",
                    "permitted_direction_source", "centerline_source", "notice_erection_source",
                    "notice_authority_source", "notice_exact_content_source",
                    "notice_conformity_source", "notice_extent_source",
                    "person_identity_source", "vehicle_identity_source", "halt_purpose_source",
                    "service_activity_source", "occupancy_source"):
            context[key] = "synthetic-unit-fixture:" + key
        write(self.context, context)
        with self.trace.open("w") as stream:
            for i in range(900):
                stream.write(json.dumps({"frame": i, "time_s": i / 20,
                                         "vehicle_speed_mps": 0,
                                         "vehicle_center_xy_m": [10, 3],
                                         "vehicle_body_polygon_xy_m": [[9, 2], [11, 2], [11, 4], [9, 4]]}) + "\n")
        streams = {}
        for view in ("overview", "approach", "reference_corner", "driver_reference"):
            path = root / (view + ".mkv")
            path.write_bytes(view.encode())
            streams[view] = {"path": path.name, "sha256": sha(path), "fps": 20,
                             "frame_count": 900}
        write(self.cameras, {"assignment_id": ASSIGNMENT, "case_id": CASE,
                             "fps": 20, "frame_count": 900, "streams": streams})
        write(self.receipt, {"assignment_id": ASSIGNMENT, "case_id": CASE,
                             "source_kind": "original_native_capture", "diagnostic_fixture": False,
                             "fps": 20, "frame_count": 900, "context_sha256": sha(self.context),
                             "trace_sha256": sha(self.trace),
                             "camera_manifest_sha256": sha(self.cameras)})

    def test_full_protocol_source_binding(self):
        with patch("saved_finalizer.inspect_video") as probe:
            result = finalize(CASE, self.context, self.trace, self.receipt, self.cameras)
        self.assertEqual(probe.call_count, 4)
        self.assertEqual(len(result["samples"]), 900)
        self.assertEqual(result["statutory_disposition"], "unresolved_pending_source_review")

    def test_changed_camera_manifest_rejected(self):
        data = json.loads(self.cameras.read_text())
        data["streams"]["overview"]["sha256"] = "0" * 64
        write(self.cameras, data)
        with self.assertRaisesRegex(ValueError, "manifest seal"):
            finalize(CASE, self.context, self.trace, self.receipt, self.cameras)

    def test_short_capture_rejected(self):
        data = json.loads(self.receipt.read_text())
        data["frame_count"] = 899
        write(self.receipt, data)
        with self.assertRaisesRegex(ValueError, "original 20 Hz frame count"):
            finalize(CASE, self.context, self.trace, self.receipt, self.cameras)

    def test_unreviewed_activity_intervention_rejected(self):
        data = json.loads(self.context.read_text())
        data["activity_request"] = "travel"
        write(self.context, data)
        receipt = json.loads(self.receipt.read_text())
        receipt["context_sha256"] = sha(self.context)
        write(self.receipt, receipt)
        with patch("saved_finalizer.inspect_video"):
            with self.assertRaisesRegex(ValueError, "activity_request"):
                finalize(CASE, self.context, self.trace, self.receipt, self.cameras)


if __name__ == "__main__":
    unittest.main()
