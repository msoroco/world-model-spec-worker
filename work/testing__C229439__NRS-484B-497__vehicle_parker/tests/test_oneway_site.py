import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRATCH = ROOT.parents[1] / ".runtime-work" / "c229439-497-owner-nov26" / "site-tests"
SCRATCH.mkdir(parents=True, exist_ok=True)
SPEC = importlib.util.spec_from_file_location("oneway_site", ROOT / "oneway_site.py")
SITE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = SITE
SPEC.loader.exec_module(SITE)


class SiteTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(dir=SCRATCH)
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name)
        self.case_id = SITE.ASSIGNMENT + "__left_park_no_device"
        self.packets = {
            "map": {"map_id": "fixture-map", "opendrive_sha256": "a" * 64},
            "roadway": {"roadway_polygon_xy": [[0, -6], [30, -6], [30, 6], [0, 6]],
                        "origin_xy": [0, 0], "forward_xy": [1, 0],
                        "marked_lanes": [{"lane_id": -1, "marking_source": "original-markings",
                                          "direction_source": "original-heading", "direction_with_forward": True},
                                         {"lane_id": -2, "marking_source": "original-markings",
                                          "direction_source": "original-heading", "direction_with_forward": True}]},
            "restriction": {"one_way": True, "authority_source": "original-authority",
                            "scope_source": "original-scope"},
            "device_inventory": {"kind": "none", "devices": [], "inventory_source": "original-inventory"},
            "authority": {"source": "original-authority"},
            "purpose": {"source": "original-purpose"},
            "person": {"source": "original-parker"},
        }
        self.site = {"assignment_id": SITE.ASSIGNMENT, "case_id": self.case_id,
                     "target_xy": [20, 3], "approach_xy": [3, 3],
                     "target_heading_deg": 0, "sources": {}}
        self.save()

    def save(self):
        for name, packet in self.packets.items():
            source = self.path / (name + ".json")
            source.write_text(json.dumps(packet) + "\n", encoding="utf-8")
            self.site["sources"][name] = {"path": source.name, "sha256": SITE.sha(source)}
        self.site_path = self.path / "site.json"
        self.site_path.write_text(json.dumps(self.site) + "\n", encoding="utf-8")

    def test_reviewed_one_way_two_lane_geometry(self):
        site, packets = SITE.load_site(self.site_path, self.case_id)
        self.assertEqual(len(packets["roadway"]["marked_lanes"]), 2)
        self.assertEqual(site["target_xy"], [20, 3])

    def test_changed_original_source_rejected(self):
        (self.path / "roadway.json").write_text("{}\n", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "hash differs"):
            SITE.load_site(self.site_path, self.case_id)

    def test_unofficial_device_needs_original_instruction_and_space(self):
        self.packets["device_inventory"] = {"kind": "unofficial_park_permit",
            "devices": [{"device_id": "one", "instruction_source": "original-sign",
                         "erection_source": "original-installation",
                         "official_status_source": "original-authority",
                         "governed_space_source": "original-scope",
                         "governed_space_polygon_xy": [[15, 0], [25, 0], [25, 5], [15, 5]],
                         "prop_blueprint_id": "static.prop.sign", "prop_pose": {"x": 20}}],
            "inventory_source": "original-inventory"}
        self.save()
        SITE.load_site(self.site_path, self.case_id)
        del self.packets["device_inventory"]["devices"][0]["official_status_source"]
        self.save()
        with self.assertRaisesRegex(ValueError, "official_status_source"):
            SITE.load_site(self.site_path, self.case_id)

    def test_target_must_be_inside_roadway(self):
        self.site["target_xy"] = [20, 9]
        self.save()
        with self.assertRaisesRegex(ValueError, "target/approach"):
            SITE.load_site(self.site_path, self.case_id)


if __name__ == "__main__":
    unittest.main()
