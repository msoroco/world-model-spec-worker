import hashlib
import json
import sys
import unittest
from pathlib import Path

PACKAGE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE))

from build_crest_opendrive import check_source_geometry
from site_construction import validate_site


class ApproachBranchProofTests(unittest.TestCase):
    def test_at_and_beyond_branch_sources_bind_geometry_and_distinct_rays(self):
        for suffix, station, bracket in (("at", 152.4, [152.4, 152.4]),
                                         ("beyond", 160.0, [160.0, 160.125])):
            for branch in ("near-a", "near-b", "approach-a", "approach-b"):
                name = suffix + "-" + branch
                with self.subTest(name=name):
                    folder = PACKAGE / ("branch-proof-" + name)
                    site_path = folder / ("diagnostic-site-crest-" + suffix + ".json")
                    site = validate_site(json.loads(site_path.read_text()))
                    self.assertAlmostEqual(
                        abs(site["occluder"]["center_xyz_m"][0] - site["turn_site_xyz_m"][0])
                        - site["occluder"]["half_extent_xyz_m"][0], station)
                    self.assertEqual(site["source_status"], "diagnostic_fixture")
                    self.assertTrue(check_source_geometry(
                        (PACKAGE / "native-map-plan/crest-road.xodr").read_text(), site))
                    if suffix == "beyond":
                        for lane in site["incoming_lanes"].values():
                            self.assertEqual(lane["stations"][-1]["distance_to_turn_m"], 180)
                    source = folder / "sources/capture/evidence.jsonl"
                    lines = source.read_text().splitlines()
                    self.assertEqual(len(lines), 1100)
                    direction = site["occluder"]["target_direction"]
                    blocked_lane = site["incoming_lanes"][direction]["lane_id"]
                    for index in (0, 400, 1099):
                        packet = json.loads(lines[index])
                        rays = {row["lane_id"]: row for row in packet["visibility"]["approaches"]}
                        self.assertEqual(set(rays), {-1, 1})
                        self.assertEqual(rays[blocked_lane]["any_body_sight_horizon"]["bracket_m"], bracket)
                        self.assertTrue(rays[blocked_lane]["any_sample_clear_at_probe"])

    def test_transformed_sources_bind_all_crest_placements_and_directions(self):
        index = json.loads((PACKAGE / "crest-branch-proof-index.json").read_text())
        self.assertEqual(len(index["branches"]), 4)
        for branch in index["branches"]:
            name = branch["name"]
            with self.subTest(name=name):
                folder = PACKAGE / ("branch-proof-" + name)
                site_path = folder / "diagnostic-site-crest-short.json"
                site = validate_site(json.loads(site_path.read_text()))
                self.assertEqual(site["turn_site_xyz_m"][0],
                                 -40 if branch["placement"] == "approach_to_crest" else 0)
                self.assertEqual(site["occluder"]["target_direction"], branch["occluded_direction"])
                self.assertAlmostEqual(
                    abs(site["occluder"]["center_xyz_m"][0] - site["turn_site_xyz_m"][0])
                    - site["occluder"]["half_extent_xyz_m"][0], 150.0)
                self.assertTrue(check_source_geometry(
                    (PACKAGE / "native-map-plan/crest-road.xodr").read_text(), site))
                digest = hashlib.sha256(site_path.read_bytes()).hexdigest()
                config = json.loads((folder / "config.json").read_text())
                self.assertEqual(config["site_source"]["sha256"], digest)
                motion = (folder / "sources/motion_history.jsonl").read_text().splitlines()
                evidence = (folder / "sources/capture/evidence.jsonl").read_text().splitlines()
                self.assertEqual(len(motion), 1100)
                self.assertEqual(len(evidence), 1100)
                for sample in (0, 400, 1099):
                    actor = json.loads(motion[sample])
                    native = json.loads(evidence[sample])
                    self.assertEqual(actor["site_source_sha256"], digest)
                    self.assertEqual(actor["ego"]["location_xyz_m"], native["ego"]["position_m"])
                    self.assertEqual(actor["approaches"]["approach_a"]["road_lane"], [10, -1])
                    self.assertEqual(actor["approaches"]["approach_b"]["road_lane"], [10, 1])
                    rays = {r["lane_id"]: r for r in native["visibility"]["approaches"]}
                    blocked_lane = -1 if branch["occluded_direction"] == "approach_a" else 1
                    self.assertEqual(rays[blocked_lane]["any_body_sight_horizon"]["bound"],
                                     "first_sampled_occlusion")
                    self.assertEqual(rays[-blocked_lane]["any_body_sight_horizon"]["bound"], "at_least")
                source_manifest = json.loads((folder / "sources/capture/manifest.json").read_text())
                for source_name in ("road.xodr", "trace.jsonl"):
                    actual = hashlib.sha256((folder / "sources" / source_name).read_bytes()).hexdigest()
                    self.assertEqual(source_manifest["sources"][source_name], actual)


if __name__ == "__main__":
    unittest.main()
