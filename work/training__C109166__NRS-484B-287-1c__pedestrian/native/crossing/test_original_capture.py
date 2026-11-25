"""CPU evidence for source-bound Native crossing capture preconditions."""

import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from original_capture import check_config, validate_survey, copy_survey_media

ASSIGNMENT = "training__C109166__NRS-484B-287-1c__pedestrian"


class Junction:
    def __init__(self, ident):
        self.id = ident


class Waypoint:
    is_junction = True

    def __init__(self, ident):
        self.ident = ident

    def get_junction(self):
        return Junction(self.ident)


class Map:
    def to_opendrive(self):
        return "<OpenDRIVE>original map</OpenDRIVE>"

    def generate_waypoints(self, spacing):
        assert spacing == 2.0
        return [Waypoint(101), Waypoint(102)]

    def get_crosswalks(self):
        return [type("Point", (), {"x": 40.0})()]


class Light:
    type_id = "traffic.traffic_light"

    def __init__(self, ident, opendrive):
        self.id = ident
        self.opendrive = opendrive

    def get_opendrive_id(self):
        return self.opendrive


class World:
    def get_actors(self):
        return [Light(201, "201"), Light(202, "202")]


def survey():
    return {
        "format": "c109166-287-1c-native-survey-v1",
        "review_status": "independently_reviewed",
        "independent_reviewer": "fixture-reviewer",
        "opendrive_sha256": hashlib.sha256(Map().to_opendrive().encode()).hexdigest(),
        "adjacent_intersections_reviewed": True,
        "no_intervening_intersection_reviewed": True,
        "junction_ids": [101, 102],
        "crossing_locations": {"marked_crosswalk": 40.0, "unmarked_midblock": 60.0},
        "controls": [
            {"native_actor_id": 201, "junction_id": 101, "opendrive_id": "201",
             "official_status_reviewed": True, "source_media_path": "control-1.txt",
             "source_media_sha256": "pending"},
            {"native_actor_id": 202, "junction_id": 102, "opendrive_id": "202",
             "official_status_reviewed": True, "source_media_path": "control-2.txt",
             "source_media_sha256": "pending"},
        ],
        "marked_crosswalk": {"original_marking_reviewed": True,
                             "polygon_xy_m": [[38, -4], [42, -4], [42, 4], [38, 4]],
                             "source_media_path": "marking.txt", "source_media_sha256": "pending"},
        "map_source": {"source_media_path": "map.txt", "source_media_sha256": "pending"},
        "roadway_boundary": {"entry_y_m": -4.0},
    }


class CapturePreconditions(unittest.TestCase):
    def test_candidate_and_exact_profile(self):
        for name in ("marked_crosswalk", "unmarked_midblock"):
            for candidate, height in (("primary", 5.0), ("fallback1", 3.0)):
                config = {"assignment_id": ASSIGNMENT, "case_id": ASSIGNMENT + "__" + name,
                          "requested_crossing_location": name, "candidate_id": candidate,
                          "rate_hz": 20, "duration_s": 30, "frames": 600,
                          "camera_dimensions": {"overview": [1920, 1080],
                                                "approach": [1280, 720],
                                                "reference_corner": [1280, 720],
                                                "driver_reference": [1280, 720]},
                          "detail_camera_height_m": height}
                self.assertEqual(check_config(config)["frames"], 600)
                config["detail_camera_height_m"] = 1
                with self.assertRaisesRegex(ValueError, "Candidate camera-height"):
                    check_config(config)

    def test_live_map_and_controls_are_required(self):
        original = survey()
        self.assertEqual([actor.id for actor in validate_survey(original, Map(), World())],
                         [201, 202])
        for field, bad in (("adjacent_intersections_reviewed", False),
                           ("no_intervening_intersection_reviewed", False),
                           ("junction_ids", [101, 103]),
                           ("crossing_locations", {"marked_crosswalk": 40, "unmarked_midblock": 40})):
            altered = json.loads(json.dumps(original))
            altered[field] = bad
            with self.assertRaises(ValueError):
                validate_survey(altered, Map(), World())
        altered = json.loads(json.dumps(original))
        altered["controls"][1]["native_actor_id"] = 201
        with self.assertRaisesRegex(ValueError, "Surveyed official control"):
            validate_survey(altered, Map(), World())

    def test_original_media_bytes_are_bound(self):
        original = survey()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source"
            output = root / "attempt"
            source.mkdir()
            output.mkdir()
            records = [original["map_source"], original["marked_crosswalk"],
                       *original["controls"]]
            for item in records:
                path = source / item["source_media_path"]
                path.write_text(item["source_media_path"])
                item["source_media_sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
            copied = copy_survey_media(original, source, output)
            self.assertEqual(len(copied), 4)
            self.assertTrue((output / "native-survey-media" / "control-1.txt").is_file())
            (source / "control-1.txt").write_text("tampered")
            with self.assertRaisesRegex(ValueError, "hash differs"):
                copy_survey_media(original, source, root / "fresh")


if __name__ == "__main__":
    unittest.main()
