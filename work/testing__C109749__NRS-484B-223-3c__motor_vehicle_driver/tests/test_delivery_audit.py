import copy
import hashlib
import importlib.util
import json
import pathlib
import tempfile
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("delivery_audit", ROOT / "delivery_audit.py")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def write_json(root, name, data):
    source = root / name
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_text(json.dumps(data, sort_keys=True) + "\n", encoding="utf-8")
    return {"path": name, "sha256": hashlib.sha256(source.read_bytes()).hexdigest()}


def fixture(root, merge=True):
    highway = write_json(root, "review/highway.json", {"public_highway_review": "pending physical review"})
    design = write_json(root, "native/lane_design.json", {"lane_design": "single_shared_bidirectional_center_turn_only"})
    lanes = ["approach", "shared_center_turn", "shared_center_turn", "receiving_through" if merge else "shared_center_turn"]
    samples = [{"frame": 100 + i, "body_centre_xy_m": [float(i * 5), 0.0], "lane": lane,
                "left_turn_onto_highway_complete": i == 1, "merged_into_through_lane": merge and i == 3}
               for i, lane in enumerate(lanes)]
    trace = {"source": {"path": "native/trace.json"}, "highway_context_source": highway,
             "lane_design_source": design, "lane_design": "single_shared_bidirectional_center_turn_only",
             "samples": samples}
    original = write_json(root, "native/trace.json", trace)
    views = {view: "camera/" + view + "/%06d.png" for view in MODULE.VIEWS}
    mapping = write_json(root, "native/frame_map.json", {"fps": 20, "frames": [
        {"frame": row["frame"], "camera_sources": views} for row in samples]})
    delivered = MODULE._MEASUREMENT.measure_center_lane_distance(trace)
    return {"case_id": "exact-case", "attempt_id": "native-attempt", "original_trace": original,
            "highway_context_source": highway, "lane_design_source": design,
            "frame_map_source": mapping, "delivered_measurement": delivered}


class DeliveryAuditTests(unittest.TestCase):
    def test_recomputes_original_saved_trace_and_four_camera_join(self):
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            receipt = fixture(root)
            outcome = MODULE.audit_saved_delivery(root, receipt)
            self.assertEqual(outcome["verified_frame_count"], 4)
            self.assertTrue(outcome["measured"]["merge_observed"])
            self.assertIsNone(outcome["physical_acceptance"])

    def test_censored_no_merge_does_not_invent_merge_frame(self):
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            receipt = fixture(root, merge=False)
            outcome = MODULE.audit_saved_delivery(root, receipt)
            self.assertIsNone(outcome["measured"]["merge_frame"])
            self.assertTrue(outcome["measured"]["censored"])

    def test_rejects_tampered_original_trace(self):
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            receipt = fixture(root)
            (root / "native/trace.json").write_text("{}\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "source hash mismatch"):
                MODULE.audit_saved_delivery(root, receipt)

    def test_rejects_receipt_arithmetic_substitution(self):
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            receipt = fixture(root)
            receipt["delivered_measurement"]["distance_ft"] = 49.0
            with self.assertRaisesRegex(ValueError, "delivered distance mismatch"):
                MODULE.audit_saved_delivery(root, receipt)

    def test_rejects_unbound_context_and_missing_camera(self):
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            receipt = fixture(root)
            wrong = copy.deepcopy(receipt)
            wrong["highway_context_source"] = wrong["lane_design_source"]
            with self.assertRaisesRegex(ValueError, "binding differ"):
                MODULE.audit_saved_delivery(root, wrong)
            frame_map = json.loads((root / "native/frame_map.json").read_text(encoding="utf-8"))
            del frame_map["frames"][2]["camera_sources"]["driver_reference"]
            receipt["frame_map_source"] = write_json(root, "native/frame_map.json", frame_map)
            with self.assertRaisesRegex(ValueError, "four-camera"):
                MODULE.audit_saved_delivery(root, receipt)

    def test_rejects_missing_frame_and_path_escape(self):
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            receipt = fixture(root)
            frame_map = json.loads((root / "native/frame_map.json").read_text(encoding="utf-8"))
            frame_map["frames"].pop()
            receipt["frame_map_source"] = write_json(root, "native/frame_map.json", frame_map)
            with self.assertRaisesRegex(ValueError, "does not join"):
                MODULE.audit_saved_delivery(root, receipt)
            receipt["original_trace"]["path"] = "../trace.json"
            with self.assertRaisesRegex(ValueError, "escapes attempt"):
                MODULE.audit_saved_delivery(root, receipt)


if __name__ == "__main__":
    unittest.main()
