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
from parking_sweep_feasibility import reviewed_candidate_angles, reviewed_placement_grid


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
    def test_reviewed_placement_grid_maps_full_body_feasibility(self):
        with TemporaryDirectory() as tmp:
            path, item = survey(tmp)
            item["context"]["roadway_polygon_xy_m"] = [[-25, 0], [25, 0],
                                                          [25, 4], [-25, 4]]
            path.write_text(json.dumps(item))
            packet = acquire(NativeMap(), path, tmp, Path(tmp) / "attempt")
            grid = reviewed_placement_grid(packet, packet.parent,
                                           edge_offsets_m=(1.0, 2.0, 3.0))
            self.assertEqual(grid["source_packet_sha256"],
                             hashlib.sha256(packet.read_bytes()).hexdigest())
            self.assertEqual([row["edge_offset_m"] for row in grid["offsets"]],
                             [1.0, 2.0, 3.0])
            self.assertNotEqual(grid["offsets"][0]["feasible_angles_deg"],
                                grid["offsets"][1]["feasible_angles_deg"])
            self.assertFalse(grid["motion_verified"])
            self.assertEqual(grid["legal_judgment"], "unresolved")

    def test_reviewed_placement_grid_rejects_invalid_offsets_and_stale_source(self):
        with TemporaryDirectory() as tmp:
            path, _ = survey(tmp)
            packet = acquire(NativeMap(), path, tmp, Path(tmp) / "attempt")
            with self.assertRaisesRegex(ValueError, "positive distinct increasing"):
                reviewed_placement_grid(packet, packet.parent, edge_offsets_m=(2.0, 1.0))
            with self.assertRaisesRegex(ValueError, "positive distinct increasing"):
                reviewed_placement_grid(packet, packet.parent, edge_offsets_m=(1.0, 1.0))
            (packet.parent / "reviewed_sources/activity.txt").write_text("changed\n")
            with self.assertRaisesRegex(ValueError, "source hash changed"):
                reviewed_placement_grid(packet, packet.parent)

    def test_reviewed_polygon_sweep_binds_packet_and_full_footprint(self):
        with TemporaryDirectory() as tmp:
            path, _ = survey(tmp)
            packet = acquire(NativeMap(), path, tmp, Path(tmp) / "attempt")
            result = reviewed_candidate_angles(packet, packet.parent)
            self.assertEqual([row["angle_deg"] for row in result["samples"]],
                             list(range(0, 91, 10)))
            self.assertTrue(result["all_footprints_fit"])
            self.assertEqual(result["source_packet_sha256"],
                             hashlib.sha256(packet.read_bytes()).hexdigest())
            self.assertFalse(result["motion_verified"])

    def test_reviewed_polygon_sweep_reports_angle_that_leaves_road(self):
        with TemporaryDirectory() as tmp:
            path, item = survey(tmp)
            item["context"]["roadway_polygon_xy_m"] = [[-25, 0], [25, 0],
                                                           [25, 3], [-25, 3]]
            path.write_text(json.dumps(item))
            packet = acquire(NativeMap(), path, tmp, Path(tmp) / "attempt")
            result = reviewed_candidate_angles(packet, packet.parent, edge_offset_m=1.5)
            self.assertFalse(result["all_footprints_fit"])
            self.assertFalse(result["samples"][-1]["full_footprint_inside_reviewed_roadway"])

    def test_reviewed_polygon_sweep_rejects_changed_source(self):
        with TemporaryDirectory() as tmp:
            path, _ = survey(tmp)
            packet = acquire(NativeMap(), path, tmp, Path(tmp) / "attempt")
            (packet.parent / "reviewed_sources/activity.txt").write_text("changed\n")
            with self.assertRaisesRegex(ValueError, "source hash changed"):
                reviewed_candidate_angles(packet, packet.parent)

    def test_reviewed_polygon_sweep_rejects_changed_survey(self):
        with TemporaryDirectory() as tmp:
            path, _ = survey(tmp)
            packet = acquire(NativeMap(), path, tmp, Path(tmp) / "attempt")
            (packet.parent / "reviewed-survey.json").write_text("{}\n")
            with self.assertRaisesRegex(ValueError, "survey and map source join"):
                reviewed_candidate_angles(packet, packet.parent)

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
