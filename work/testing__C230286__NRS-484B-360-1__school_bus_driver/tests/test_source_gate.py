import os
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from package_spec import AID, CAMERA_NAMES
from school_bus import construct


class SchoolBusSourceGateTests(unittest.TestCase):
    def site(self, suffix="pupil_trip_55_mph"):
        return {"assignment_id": AID, "case_id": AID + "__" + suffix,
                "source_kind": "original_native_map_geometry", "reviewed_original_native_site": True,
                "source_id": "synthetic-only", "map_name": "synthetic", "map_sha256": "a" * 64,
                "road_route": {"source_kind": "native_map_lane_geometry", "continuous_drivable": True,
                               "clear_run_length_m": 950, "minimum_width_m": 3.5},
                "sidewalk": {"source_id": "synthetic-sidewalk", "relation": "access"},
                "school_bus_classification": {"qualifying_definition_branch": "synthetic branch",
                                              "source": "synthetic-definition", "all_exclusions_reviewed": True,
                                              "reviewed_facts": ["synthetic"],
                                              "exclusion_dispositions": ["synthetic"]},
                "driver_actor_id": "driver", "bus_identity_source": "synthetic-identity",
                "trip": {"direction": "to_school", "source": "synthetic-trip",
                         "pupil_count": 12, "pupil_presence_source": "synthetic-pupils",
                         "active_transport_intervals_s": [[0, 45]]},
                "requested_target_mph": 55, "requested_active_transport_phase": True,
                "native_spawn": {"source_id": "synthetic-pose", "blueprint_id": "vehicle.synthetic",
                                 "pose_xyz_ypr": [0, 0, 0, 0, 0, 0]},
                "rate_hz": 20, "duration_frames": 900, "cameras": CAMERA_NAMES}

    def test_exact_speed_cases(self):
        for speed in (54, 55, 56):
            site = self.site(f"pupil_trip_{speed}_mph")
            site["requested_target_mph"] = speed
            request = construct(site, site["case_id"])
            self.assertAlmostEqual(request["target_speed_mph"], speed)

    def test_nontransport_interval(self):
        site = self.site("nontransport_56_mph")
        site["requested_target_mph"] = 56
        site["requested_active_transport_phase"] = False
        site["trip"]["active_transport_intervals_s"] = [[0, 10]]
        self.assertFalse(construct(site, site["case_id"])["requested_active_transport_phase"])

    def test_unreviewed_exclusions_rejected(self):
        site = self.site()
        site["school_bus_classification"]["all_exclusions_reviewed"] = False
        with self.assertRaisesRegex(ValueError, "exclusions"):
            construct(site, site["case_id"])

    def test_missing_pupil_source_rejected(self):
        site = self.site()
        del site["trip"]["pupil_presence_source"]
        with self.assertRaisesRegex(ValueError, "presence source"):
            construct(site, site["case_id"])

    def test_short_route_rejected(self):
        site = self.site()
        site["road_route"]["clear_run_length_m"] = 600
        with self.assertRaisesRegex(ValueError, "corridor"):
            construct(site, site["case_id"])


if __name__ == "__main__":
    unittest.main()
