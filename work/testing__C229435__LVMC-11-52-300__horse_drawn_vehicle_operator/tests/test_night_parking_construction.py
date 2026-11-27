import hashlib
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("night_parking_construction", ROOT / "night_parking_construction.py")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class SiteTests(unittest.TestCase):
    def test_original_sources_geometry_and_duration(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd() / ".runtime-work") as tmp:
            root = Path(tmp)
            sources = {}
            for label in ("opendrive", "municipal_boundary", "street_status", "vehicle_build", "person_activity"):
                path = root / (label + ".txt")
                path.write_text("reviewed " + label + " source\n")
                sources[label] = {"path": path.name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
            packet = {
                "format": "night-parking-reviewed-site-v1",
                "sources": sources,
                "native_map_name": "ReviewedMap",
                "native_opendrive_sha256": sources["opendrive"]["sha256"],
                "geometry": {
                    "street_polygon_xy_m": [[0, 0], [30, 0], [30, 10], [0, 10]],
                    "municipal_polygon_xy_m": [[-5, -5], [35, -5], [35, 15], [-5, 15]],
                    "carriage_park_xy_m": [5, 5],
                    "other_vehicle_xy_m": [20, 5],
                    "carriage_body_dimensions_m": [4, 2],
                    "other_vehicle_body_dimensions_m": [4, 2],
                },
                "source_review": {key: "reviewed" for key in (
                    "carriage_transport_capable", "carriage_motive_power", "vehicle_exclusions",
                    "responsible_person", "street_public_access", "municipal_jurisdiction")},
                "native_actors": {"carriage_blueprint": "custom-carriage", "other_vehicle_blueprint": "car", "responsible_person_blueprint": "walker"},
            }
            packet_path = root / "site.json"
            packet_path.write_text(json.dumps(packet) + "\n")
            self.assertEqual(MODULE.validate_site(packet_path, root), packet)
            case = {"case_id": "exact", "design": {"duration_s": 1801, "start_local": "02:00:00", "vehicle_class": "nonmotor", "purpose": "parking"}}
            self.assertEqual(MODULE.plan_case(case, packet)["original_frame_count"], 36101)
            self.assertEqual(MODULE.plan_case(case, packet)["parked_first_index"], 40)
            self.assertEqual(MODULE.plan_case(case, packet)["parked_last_index"], 36060)
            packet["geometry"]["other_vehicle_xy_m"] = [40, 5]
            packet_path.write_text(json.dumps(packet) + "\n")
            with self.assertRaisesRegex(ValueError, "street and city"):
                MODULE.validate_site(packet_path, root)
            packet["geometry"]["other_vehicle_xy_m"] = [20, 5]
            sources["vehicle_build"]["sha256"] = "0" * 64
            packet_path.write_text(json.dumps(packet) + "\n")
            with self.assertRaisesRegex(ValueError, "source hash"):
                MODULE.validate_site(packet_path, root)


if __name__ == "__main__":
    unittest.main()
