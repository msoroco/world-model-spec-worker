"""Source-packet checks prevent diagnostic or changed site adoption."""

import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
SPEC = importlib.util.spec_from_file_location("reviewed_site", ROOT / "reviewed_site.py")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class ReviewedSiteTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=os.environ["TMPDIR"])
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def add(self, path, value):
        p = self.root / path
        p.write_text(value if isinstance(value, str) else json.dumps(value) + "\n")
        return {"path": path, "sha256": hashlib.sha256(p.read_bytes()).hexdigest()}

    def site(self):
        site = {"source_kind": "reviewed_original_site", "cell_id": "C422976",
                "school_lane_control": "school_crosswalk"}
        site["opendrive"] = self.add("road.xodr", "<OpenDRIVE/>\n")
        site["nearest_side_geometry"] = self.add("geometry.json", {
            "nearest_side_station_m": 100.0, "approach_lane_id": -1,
            "school_lane_polygon_xy": [[0, 0], [1, 0], [1, 3], [0, 3]]})
        for name in ("municipal_jurisdiction", "vehicle_reference_point",
                     "human_actor", "device_actor", "child_actor"):
            site[name] = self.add(name + ".json", {"reviewed": True})
        return self.add("site.json", site)

    def test_source_bound_plan_for_exact_case(self):
        ref = self.site()
        case = MODULE.ASSIGNMENT + "__human_warning_stop_51ft_go"
        plan = MODULE.plan(self.root, ref, case)
        self.assertAlmostEqual(plan["stop_reference_station_target_m"], 100 - 51 * .3048)
        self.assertEqual(plan["legal_judgment"], "unresolved")

    def test_stale_site_and_map_are_rejected(self):
        ref = self.site()
        case = MODULE.ASSIGNMENT + "__human_warning_stop_51ft_go"
        (self.root / "road.xodr").write_text("changed\n")
        with self.assertRaisesRegex(ValueError, "bytes changed: opendrive"):
            MODULE.plan(self.root, ref, case)
        (self.root / "site.json").write_text("changed\n")
        with self.assertRaisesRegex(ValueError, "site bytes changed"):
            MODULE.plan(self.root, ref, case)

    def test_path_escape_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "escapes"):
            MODULE.plan(self.root, {"path": "../outside", "sha256": "a" * 64},
                        MODULE.ASSIGNMENT + "__human_warning_stop_51ft_go")


if __name__ == "__main__":
    unittest.main()
