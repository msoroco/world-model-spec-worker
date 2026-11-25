import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from reviewed_site import load_review, verify_native_map


class ReviewSiteTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.case_id = "testing__C150911__NRS-484B-293__pedestrian__forward_right"
        payloads = {
            "opendrive": "<OpenDRIVE>original</OpenDRIVE>",
            "crosswalk": {"crosswalk_id": "cw-1", "one_way_road_id": 7,
                "entry_center": [0, 0], "exit_center": [10, 0],
                "crosswalk_width_m": 4,
                "crosswalk_vertices_xy_m": [[0, -2], [0, 2], [10, 2], [10, -2]]},
            "pedestrian_access": {"pedestrian_access": True, "method": "original sidewalk readback"},
            "signal": {"governing_signal": "none_read_back"},
            "obstacles": {"obstacles": []}, "participants": {"participants": []},
            "cameras": {name: {"location_xyz_m": [1, 2, 3],
                "pitch_yaw_roll_deg": [0, 0, 0]} for name in
                ("overview", "approach", "reference_corner", "driver_reference")}}
        sources = {}
        for name, value in payloads.items():
            path = self.root / (name + (".xodr" if name == "opendrive" else ".json"))
            path.write_text(value if isinstance(value, str) else json.dumps(value))
            sources[name] = {"path": path.name,
                             "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
        self.review = self.root / "review.json"
        self.review.write_text(json.dumps({"case_id": self.case_id,
            "cell_id": "C150911", "review_status": "original_native_reviewed",
            "pedestrian_source_sha256": "original-blueprint-source",
            "sources": sources}))

    def test_source_hash_and_native_crosswalk_readback(self):
        reviewed = load_review(self.review, self.case_id)

        class Point:
            def __init__(self, x, y):
                self.x, self.y = x, y

        class Waypoint:
            road_id = 7

        class Map:
            def to_opendrive(self):
                return "<OpenDRIVE>original</OpenDRIVE>"

            def get_crosswalks(self):
                return [Point(*xy) for xy in ([0, -2], [0, 2], [10, 2], [10, -2])]

            def get_topology(self):
                return [(Waypoint(), Waypoint())]

        class World:
            def get_map(self):
                return Map()

        self.assertTrue(verify_native_map(World(), reviewed))
        (self.root / "crosswalk.json").write_text("{}")
        with self.assertRaisesRegex(ValueError, "reviewed source changed"):
            load_review(self.review, self.case_id)


if __name__ == "__main__":
    unittest.main()
