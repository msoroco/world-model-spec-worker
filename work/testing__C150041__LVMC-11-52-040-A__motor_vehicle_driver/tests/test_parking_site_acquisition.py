"""Source acquisition requires genuine map bytes and explicit review inputs."""
import copy
import hashlib
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from parking_site_acquisition import acquire
from parking_scene import build


XODR = '<OpenDRIVE><road name="straight" id="1" length="80" junction="-1" /></OpenDRIVE>'


class NativeMap:
    name = "TestOneWay"

    def to_opendrive(self):
        return XODR


def survey(root):
    root = Path(root)
    sources = {}
    for name in ("one_way_direction", "activity", "chapter_exceptions"):
        path = root / (name + ".txt")
        path.write_text("Reviewed source for " + name + "\n")
        sources[name] = {"path": path.name,
                         "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                         "reviewer": "fixture reviewer", "citation": "fixture only"}
    item = {"assignment_id": ROOT.name, "review_status": "reviewed",
            "survey_reviewer": "fixture reviewer", "survey_citation": "fixture only",
            "native_map": {"name": "TestOneWay",
                           "opendrive_sha256": hashlib.sha256(XODR.encode()).hexdigest()},
            "sources": sources,
            "context": {"roadway_kind": "one_way_road",
                        "responsible_person_role": "motor_vehicle_driver",
                        "activity": "park", "chapter_exception_review": "unresolved",
                        "road_edge_xy_m": [[-25, 0], [25, 0]],
                        "roadway_polygon_xy_m": [[-25, 0], [25, 0], [25, 8], [-25, 8]],
                        "lawful_travel_xy": [1, 0]}}
    path = root / "survey.json"
    path.write_text(json.dumps(item))
    return path, item


class ParkingSiteAcquisitionTests(unittest.TestCase):
    def test_retains_native_bytes_and_constructs_source_bound_case(self):
        with TemporaryDirectory() as tmp:
            path, item = survey(tmp)
            packet = acquire(NativeMap(), path, tmp, Path(tmp) / "attempt")
            self.assertEqual((packet.parent / "reviewed_sources/native-map.xodr").read_text(), XODR)
            self.assertEqual(json.loads(packet.read_text())["survey_sha256"],
                             hashlib.sha256(path.read_bytes()).hexdigest())
            scene = build(packet, packet.parent, "park_parallel_lawful")
            self.assertEqual(scene["case_id"], ROOT.name + "__park_parallel_lawful")
            self.assertFalse(scene["physical_realization_claimed"])
            with self.assertRaises(FileExistsError):
                acquire(NativeMap(), path, tmp, Path(tmp) / "attempt")

    def test_stale_map_and_source_are_rejected(self):
        with TemporaryDirectory() as tmp:
            path, item = survey(tmp)
            wrong = copy.deepcopy(item)
            wrong["native_map"]["opendrive_sha256"] = "0" * 64
            path.write_text(json.dumps(wrong))
            with self.assertRaisesRegex(ValueError, "Native map differs"):
                acquire(NativeMap(), path, tmp, Path(tmp) / "stale-map")
            path.write_text(json.dumps(item))
            (Path(tmp) / "activity.txt").write_text("changed\n")
            with self.assertRaisesRegex(ValueError, "source hash differs"):
                acquire(NativeMap(), path, tmp, Path(tmp) / "stale-source")

    def test_review_and_geometry_must_be_explicit(self):
        with TemporaryDirectory() as tmp:
            path, item = survey(tmp)
            item["review_status"] = "candidate"
            path.write_text(json.dumps(item))
            with self.assertRaisesRegex(ValueError, "reviewed survey required"):
                acquire(NativeMap(), path, tmp, Path(tmp) / "unreviewed")
            item["review_status"] = "reviewed"
            item["context"]["lawful_travel_xy"] = [0, 1]
            path.write_text(json.dumps(item))
            with self.assertRaisesRegex(ValueError, "conflict"):
                acquire(NativeMap(), path, tmp, Path(tmp) / "wrong-direction")
            self.assertFalse((Path(tmp) / "wrong-direction").exists())


if __name__ == "__main__":
    unittest.main()
