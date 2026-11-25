import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from native_site import read_site, validate
from native_capture_contract import DIMENSIONS


SITE = {
    "source_kind": "original_local_signal_site_inventory",
    "map_name": "ReviewedTown", "ego_blueprint_id": "vehicle.reviewed.car",
    "district_kind": "business", "maneuver": "right_turn",
    "loading_zone_actor_id": "42", "approach_start_xyz": [-70, 0, 0],
    "turn_vertex_xyz": [0, 0, 0], "outgoing_target_xyz": [0, -25, 0],
    "highway_source": "reviewed roadway survey", "district_source": "municipal district record",
    "frontage_source": "reviewed frontage inventory", "building_use_source": "reviewed building-use inventory",
    "loading_zone_source": "reviewed curb designation", "driver_source": "reviewed car and driver",
    "route_source": "reviewed lane geometry",
    "drive_speed_source": "reviewed vehicle capability", "drive_speed_m_s": 5,
    "camera_rig_source": "reviewed four-view mounting plan",
    "camera_rigs": {name: {"relative_xyz": [0, 0, 2], "relative_ypr_deg": [0, 0, 0],
                           "dimensions": list(size)} for name, size in DIMENSIONS.items()},
    "business_district_review": {"jurisdiction": "Nevada", "frontage_bounds": "reviewed segment",
                                 "building_uses": "reviewed buildings", "reviewer": "local reviewer"},
}


class NativeSiteTests(unittest.TestCase):
    def test_source_hash_and_right_turn_geometry(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "site.json"
            path.write_text(json.dumps(SITE))
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            self.assertEqual(read_site(path, digest), SITE)
            self.assertLess(validate(SITE)["signed_turn_angle_deg"], -35)
            with self.assertRaisesRegex(ValueError, "hash mismatch"):
                read_site(path, "0" * 64)

    def test_unsupported_geometry_and_authority_fail_before_world_mutation(self):
        for change, expected in (
            ({"outgoing_target_xyz": [0, 25, 0]}, "not a right turn"),
            ({"approach_start_xyz": [-20, 0, 0]}, "too short"),
            ({"district_kind": "other_area"}, "business-district right turn"),
            ({"frontage_source": ""}, "missing original signal site field"),
            ({"business_district_review": {}}, "frontage and use source required"),
            ({"diagnostic_fixture": True}, "diagnostic fixture cannot"),
        ):
            with self.subTest(change=change), self.assertRaisesRegex(ValueError, expected):
                validate({**SITE, **change})


if __name__ == "__main__":
    unittest.main()
