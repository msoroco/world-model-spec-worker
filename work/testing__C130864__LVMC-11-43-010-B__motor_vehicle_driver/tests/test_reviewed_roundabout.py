import hashlib
import json
import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from capture_roundabout import CAMERAS
from reviewed_roundabout import load_reviewed
import test_native_roundabout as source_module


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class ReviewTests(unittest.TestCase):
    def setUp(self):
        source = source_module.NativeConstructionTests("test_source_bound_case_and_two_spawns")
        source.setUp()
        self.addCleanup(source.doCleanups)
        self.source = source
        self.root = source.map_path.parent
        self.road = self.root / "original-road.xodr"
        self.road.write_text("<OpenDRIVE><header name='reviewed-map'/></OpenDRIVE>\n")
        source.packet["map_sha256"] = sha(self.road)
        source.fixture.write()
        self.placement = self.root / "original-cameras.json"
        self.placement.write_text(json.dumps({"cameras": {name: {
            "location_xyz_m": [0, 0, 3], "pitch_yaw_roll_deg": [0, 0, 0]}
            for name in CAMERAS}}) + "\n")
        self.review = self.root / "review.json"
        self.document = {"case_id": source.case, "review_status": "reviewed_original",
            "sources": {name: {"path": path.name, "sha256": sha(path)} for name, path in
                (("opendrive", self.road), ("construction_packet", source.map_path),
                 ("camera_placement", self.placement))}}
        self.write()

    def write(self):
        self.review.write_text(json.dumps(self.document) + "\n")

    def test_exact_review_binds_all_source_bytes(self):
        result = load_reviewed(self.review, self.source.case)
        self.assertEqual(result["packet"]["case_id"], self.source.case)
        self.placement.write_text(self.placement.read_text() + "changed")
        with self.assertRaisesRegex(ValueError, "review source changed"):
            load_reviewed(self.review, self.source.case)

    def test_rejects_unreviewed_source(self):
        self.document["review_status"] = "draft"
        self.write()
        with self.assertRaisesRegex(ValueError, "original roundabout source review"):
            load_reviewed(self.review, self.source.case)


if __name__ == "__main__":
    unittest.main()
