"""The site packet must retain original bytes and avoid a legal conclusion."""
import copy
import hashlib
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from source_review import validate
from parking_measurement import measure_frame
from parking_pose import construct


def fixture(root):
    root = Path(root)
    sources = {}
    for name in ("roadway", "one_way_direction", "activity", "chapter_exceptions"):
        path = root / (name + ".txt")
        path.write_text("Synthetic protocol source: " + name + "\n")
        sources[name] = {"path": path.name,
                         "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                         "reviewer": "synthetic fixture author", "citation": "fixture only"}
    packet = {"assignment_id": ROOT.name, "review_status": "reviewed", "sources": sources,
              "context": {"roadway_kind": "one_way_road",
                          "responsible_person_role": "motor_vehicle_driver",
                          "activity": "park", "chapter_exception_review": "unresolved",
                          "road_edge_xy_m": [[-20, 0], [20, 0]],
                          "roadway_polygon_xy_m": [[-20, 0], [20, 0], [20, 5], [-20, 5]],
                          "lawful_travel_xy": [1, 0]}}
    packet_path = root / "reviewed-context.json"
    packet_path.write_text(json.dumps(packet))
    return packet_path, packet


class SourceReviewTests(unittest.TestCase):
    def test_retained_geometry_and_unresolved_chapter_review(self):
        with TemporaryDirectory() as tmp:
            path, packet = fixture(tmp)
            result = validate(path, source_root=tmp)
            self.assertEqual(result["lawful_travel_xy"], (1, 0))
            self.assertEqual(result["chapter_exception_review"], "unresolved")
            self.assertEqual(result["legal_judgment"], "unresolved")
            measured = measure_frame({"frame": 0, "time_s": 0,
                                      "vehicle_forward_xy": [1, 0],
                                      "body_vertices_xy_m": [[-1, .6], [1, .6],
                                                              [1, 1.4], [-1, 1.4]]}, result)
            self.assertAlmostEqual(measured["center_edge_distance_m"], 1)
            pose = construct(result, "park_parallel_lawful")
            self.assertEqual(pose["source_packet_sha256"], result["reviewed_packet_sha256"])
            packet["review_status"] = "candidate"
            path.write_text(json.dumps(packet))
            with self.assertRaisesRegex(ValueError, "not been reviewed"):
                validate(path, source_root=tmp)

    def test_changed_bytes_or_unreviewed_direction_rejected(self):
        with TemporaryDirectory() as tmp:
            path, packet = fixture(tmp)
            (Path(tmp) / "roadway.txt").write_text("changed")
            with self.assertRaisesRegex(ValueError, "hash changed"):
                validate(path, source_root=tmp)
            (Path(tmp) / "roadway.txt").write_text("Synthetic protocol source: roadway\n")
            packet["context"]["lawful_travel_xy"] = [0, 1]
            path.write_text(json.dumps(packet))
            with self.assertRaisesRegex(ValueError, "conflict"):
                validate(path, source_root=tmp)
            packet["context"]["lawful_travel_xy"] = [1, 0]
            packet["context"]["roadway_polygon_xy_m"] = [[-20, -5], [20, -5],
                                                               [20, 5], [-20, 5]]
            path.write_text(json.dumps(packet))
            with self.assertRaisesRegex(ValueError, "does not bound one side"):
                validate(path, source_root=tmp)

    def test_source_path_and_activity_guards(self):
        with TemporaryDirectory() as tmp:
            path, packet = fixture(tmp)
            unsafe = copy.deepcopy(packet)
            unsafe["sources"]["activity"]["path"] = "../activity.txt"
            path.write_text(json.dumps(unsafe))
            with self.assertRaisesRegex(ValueError, "must be local"):
                validate(path, source_root=tmp)
            packet["context"]["activity"] = "travel"
            path.write_text(json.dumps(packet))
            with self.assertRaisesRegex(ValueError, "context incomplete"):
                validate(path, source_root=tmp)


if __name__ == "__main__":
    unittest.main()
