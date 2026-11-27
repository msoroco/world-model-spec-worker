import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from native_acquisition import capture
from audit_original_attempt import audit
from parked_construction import ASSIGNMENT

PNG = b"\x89PNG\r\n\x1a\n" + b"diagnostic-original-camera-content"


class FakeOperator:
    native_attested = False

    def __init__(self, case_id, map_bytes):
        self.case_id = case_id
        self.map_bytes = map_bytes
        self.count = 0
        self.cleaned = False
        digest = hashlib.sha256(map_bytes).hexdigest()
        sources = {name: {"path": name + ".txt", "sha256": digest} for name in
                   ("map", "highway_boundary", "dedication", "public_use",
                    "parking_permission", "vehicle_blueprint", "approach_route")}
        self.site = {
            "case_id": case_id, "source_kind": "reviewed_original_native_site",
            "public_highway_status": True, "public_dedication_reviewed": True,
            "public_vehicular_use_reviewed": True,
            "parking_permitted_at_capture_time": True, "reviewed_sources": sources,
            "highway_polygon_xy_m": [[-100, -10], [100, -10], [100, 10], [-100, 10]],
            "parking_bay_polygon_xy_m": [[-15, -9], [5, -9], [5, -3], [-15, -3]],
            "parked_vehicle_center_xy_m": [-8, -6],
            "ego_departure_entry_xy_m": [0, -2],
            "ego_departure_exit_xy_m": [30, -2],
            "parked_vehicle_center_fallback_xy_m": [-4, -6],
            "ego_departure_entry_fallback_xy_m": [4, -2],
            "ego_departure_exit_fallback_xy_m": [34, -2],
            "rear_approach_route_xy_m": [[-70, -2], [60, -2]],
            "opposing_approach_route_xy_m": [[70, 2], [-70, 2]],
            "nonconflicting_opposing_route_reviewed": True,
        }

    def get_map_packet(self, case_id):
        assert case_id == self.case_id
        return self.site

    def get_opendrive_bytes(self):
        return self.map_bytes

    def start(self, plan):
        self.plan = plan

    def read_actor_inventory(self):
        return {"ego_vehicle_id": 1, "ego_actual_blueprint": "vehicle.example",
                "ego_actual_dimensions_m": [4, 2, 1.5], "other_vehicle_id": 2,
                "other_actual_blueprint": "vehicle.example", "driver_actor_id": 3}

    def tick(self):
        frame = 1000 + self.count
        time_s = 50 + self.count / 20
        self.count += 1
        return {"frame": frame, "time_s": time_s}

    def read_activity(self, frame):
        index = frame - 1000
        return {
            "frame": frame, "time_s": 50 + index / 20,
            "source_kind": "original_native", "case_id": self.case_id,
            "ego_vehicle_id": 1, "other_vehicle_id": 2, "driver_actor_id": 3,
            "ego_center_xy_m": [-8 + min(index, 600) / 20, -6],
            "other_center_xy_m": [-70 + index / 10, -2],
            "ego_speed_mps": 0 if index < 200 else 1,
            "other_speed_mps": 2,
            "ego_in_reviewed_parking_bay": index < 200,
            "ego_on_public_highway": True,
            "parking_permitted_at_time": True,
            "driver_in_control": True,
            "other_approaching": index < 300,
            "paths_overlap": 250 < index < 280,
            "passenger_exchange": False, "goods_exchange": False,
        }

    def read_cameras(self, frame):
        time_s = 50 + (frame - 1000) / 20
        return {name: {"frame": frame, "time_s": time_s, "png": PNG}
                for name in ("overview", "approach", "reference_corner", "driver_reference")}

    def brake(self):
        self.braked = True

    def cleanup(self):
        self.cleaned = True


class NativeCaptureTests(unittest.TestCase):
    def test_original_capture_and_source_audit(self):
        case_id = ASSIGNMENT + "__rear_wait"
        operator = FakeOperator(case_id, b"reviewed opendrive source")
        temp_root = Path(os.environ["SCENARIO_PIPELINE_OUTPUT_ROOT"])
        temp_root.mkdir(parents=True, exist_ok=True)
        scratch = Path(tempfile.mkdtemp(prefix="c227890-capture-", dir=temp_root))
        original = scratch / "original-attempt"
        measured = capture(operator, case_id, original)
        self.assertTrue(operator.cleaned)
        self.assertEqual(measured["frame_count"], 900)
        self.assertEqual(audit(original, case_id)["structural_status"], "passed")
        (original / "activity-seal.json").unlink()
        with self.assertRaisesRegex((ValueError, FileNotFoundError), "source|seal"):
            audit(original, case_id)


if __name__ == "__main__":
    unittest.main()
