"""Source and original-frame tests for the exact School-Xing branch."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

import school_crossing as school


def digest(data):
    return hashlib.sha256(data).hexdigest()


class SchoolCrossingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.case = school.CASES[1]
        records = {}
        for name in school.SOURCES:
            contents = (name + ": reviewed original source fixture\n").encode()
            (self.root / (name + ".txt")).write_bytes(contents)
            records[name] = {"path": name + ".txt", "sha256": digest(contents)}
        self.site = {
            "assignment_id": school.ASSIGNMENT,
            "source_kind": "reviewed_original_native_school_crossing",
            "law_id": school.LAW, "cell_id": "C422976",
            "catalog_control": "school_crosswalk",
            "case_ids": [school.ASSIGNMENT + "__" + c.name for c in school.CASES],
            "source_records": records, "jurisdiction": "Las Vegas municipal",
            "engineer_opinion_source": "municipal_authority.txt",
            "sign_necessity_source": "municipal_authority.txt",
            "operator_id": "driver-1", "vehicle_id": "vehicle-1",
            "vehicle_class": "heavy_vehicle", "route_clearance_reviewed": True,
            "intersection_status": "intersection", "school_vicinity_reviewed": True,
            "crossing_rect_m": [0, -3, 4, 3],
            "roadway_rect_m": [-30, -4, 30, 4],
            "crossing_width_ft": 12.0, "crossing_marking": "yellow_paint",
            "sign": {"words": "School-Xing", "conspicuous_reviewed": True,
                     "placement": "curb", "advance_distance_ft": 100.0,
                     "displayed": True},
            "person": {"id": "person-1", "side_relative_to_approach": "approach_side",
                       "attempt_evidence_source": "pedestrian_source.txt",
                       "attempt_requested": True},
            "approach_direction_xy": [1, 0], "opposing_direction_xy": [-1, 0],
            "road_id": 1, "lane_id": -1, "map_sha256": "a" * 64,
            "crossing_id": "crossing-1", "sign_id": "sign-1"
        }
        self.path = self.root / "site.json"
        self.seal()

    def seal(self):
        self.path.write_text(json.dumps(self.site, sort_keys=True) + "\n")
        self.site_sha = digest(self.path.read_bytes())

    def readback(self):
        return {key: self.site[key] for key in
                ("crossing_id", "crossing_rect_m", "roadway_rect_m",
                 "crossing_width_ft", "crossing_marking", "sign_id",
                 "road_id", "lane_id", "sign")}

    def test_exact_reviewed_site_and_readback(self):
        school.source_site(self.site, self.path, self.site_sha,
                           case=self.case, native_readback=self.readback())

    def test_source_change_rejected(self):
        (self.root / "sign_installation.txt").write_text("changed\n")
        with self.assertRaisesRegex(ValueError, "source bytes changed"):
            school.source_site(self.site, self.path, self.site_sha, case=self.case)

    def test_wrong_school_xing_display_rejected(self):
        readback = self.readback()
        readback["sign"] = dict(readback["sign"], displayed=False)
        with self.assertRaisesRegex(ValueError, "Native School-Xing display"):
            school.source_site(self.site, self.path, self.site_sha,
                               case=self.case, native_readback=readback)

    def test_wrong_frozen_control_rejected(self):
        self.site["catalog_control"] = "pedestrian"
        self.seal()
        with self.assertRaisesRegex(ValueError, "frozen cell"):
            school.source_site(self.site, self.path, self.site_sha, case=self.case)

    def test_original_entry_measurement_and_frame_join(self):
        sha = self.site["source_records"]["pedestrian_source"]["sha256"]
        def row(frame, x):
            return {"source_frame_id": frame, "time_s": frame / 20,
                    "actor_id": "vehicle-1", "person_id": "person-1",
                    "road_id": 1, "lane_id": -1, "vehicle_front_xy": [x, 0],
                    "person_xy": [2, -2], "sign_displayed": True,
                    "person_attempt_source_sha256": sha,
                    "person_attempt_observed": True,
                    "person_side_relative_to_approach": "approach_side"}
        rows = [row(100, -1), row(101, 0.5)]
        got = school.measure_original(rows, self.site, self.case)
        self.assertEqual(got["entry"]["frame"], 101)
        self.assertTrue(got["entry"]["person_in_crossing"])
        rows[1]["source_frame_id"] = 103
        with self.assertRaisesRegex(ValueError, "frame sequence"):
            school.measure_original(rows, self.site, self.case)


if __name__ == "__main__":
    unittest.main()
