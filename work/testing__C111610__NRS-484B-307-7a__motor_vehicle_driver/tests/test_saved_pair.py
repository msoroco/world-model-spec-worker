import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[1]
sys.path.insert(0, str(ROOT))

from event_capture import capture_pair
from saved_pair import audit_saved_pair


class SavedPairTests(unittest.TestCase):
    def setUp(self):
        scratch = REPO / ".runtime-work/c111610-saved-pair-tests"
        scratch.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=scratch)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def attempt(self, suffix, users):
        root = self.root / suffix
        root.mkdir()
        refs = []
        for name in ("map", "signal", "route", "crosswalk"):
            path = root / (name + ".json")
            path.write_text(json.dumps({"name": name}) + "\n")
            refs.append({"path": path.name,
                         "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
        site = {"case_id": ROOT.name + "__" + suffix,
                "cell_id": "C111610", "actor": "motor_vehicle_driver",
                "original_sources": refs,
                "map_source_path": "map.json", "signal_source_path": "signal.json",
                "route_source_path": "route.json", "crosswalk_source_path": "crosswalk.json",
                "native_map_name": "TownTest", "camera_profile_sha256": "c" * 64,
                "official_head_id": "17", "ego_approach_id": "north",
                "facing_relation": True, "arrow_movement": "left",
                "ego_route_xy": [[0, -8], [0, 0], [-8, 0]],
                "intersection_polygon_xy": [[-3, -3], [3, -3], [3, 3], [-3, 3]],
                "adjacent_crosswalk_polygon_xy": [[3, -3], [6, -3], [6, 3], [3, 3]]}
        site_path = root / "site.json"
        site_path.write_text(json.dumps(site) + "\n")
        def sample(i):
            lit = i != 1
            aspect = {"frame": 100 + i, "elapsed_seconds": i / 20,
                      "head_id": "17", "facing_approach_id": "north",
                      "arrow_color": "yellow", "arrow_direction": "left",
                      "arrow_lit": lit, "source_kind": "display_sensor",
                      "source_id": "head-camera-17", "native_head_state": "Yellow",
                      "concurrent_indications": []}
            event = {"frame": 100 + i, "official_head_id": "17",
                     "facing_approach_id": "north", "arrow_movement": "left",
                     "lit_aspects": ["flashing_yellow_turn_arrow"] if lit else [],
                     "concurrent_indications": [], "ego_movement": "left",
                     "concurrently_permitted_movement": None,
                     "ego_xy": [[0, -8], [0, 0], [-8, 0]][i],
                     "other_users": users}
            return aspect, event
        capture_pair(site, root, sample, frames=3, diagnostic=True)
        return site_path, root

    def test_recomputed_exact_pair_and_tamper_rejection(self):
        left = self.attempt("arrow_clear", [])
        user = {"id": "p1", "kind": "pedestrian", "xy": [4, 0],
                "lawful_presence_source": "reviewed-crossing-log"}
        right = self.attempt("arrow_ped_crosswalk", [user])
        result = audit_saved_pair("pedestrian_crosswalk", *left, *right,
                                  diagnostic=True)
        self.assertEqual(result["format"], "c111610-source-bound-arrow-comparison-v1")
        self.assertFalse(result["physical_acceptance"])
        self.assertEqual(len(result["source_hashes"]), 2)
        event_path = right[1] / "arrow-events-original.json"
        event_path.write_text(event_path.read_text() + " ")
        with self.assertRaisesRegex(ValueError, "hash mismatch"):
            audit_saved_pair("pedestrian_crosswalk", *left, *right,
                             diagnostic=True)

    def test_fixed_source_and_region_rejections(self):
        left = self.attempt("arrow_clear", [])
        user = {"id": "p1", "kind": "pedestrian", "xy": [4, 0],
                "lawful_presence_source": "reviewed-crossing-log"}
        right = self.attempt("arrow_ped_crosswalk", [user])
        signal = right[1] / "signal.json"
        signal.write_text(json.dumps({"name": "different-signal"}) + "\n")
        site = json.loads(right[0].read_text())
        site["original_sources"][1]["sha256"] = hashlib.sha256(signal.read_bytes()).hexdigest()
        right[0].write_text(json.dumps(site) + "\n")
        with self.assertRaisesRegex(ValueError, "fixed condition differs"):
            audit_saved_pair("pedestrian_crosswalk", *left, *right,
                             diagnostic=True)
