import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from event_capture import capture_pair
from saved_finalizer import ASSIGNMENT, finalize_saved


class SavedFinalizerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        refs = []
        for name in ("map", "signal", "route", "crosswalk"):
            path = self.root / (name + ".json")
            path.write_text(json.dumps({"name": name}) + "\n")
            refs.append({"path": path.name,
                         "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
        self.site = {"cell_id": "C111610", "actor": "motor_vehicle_driver",
            "original_sources": refs, "map_source_path": "map.json",
            "signal_source_path": "signal.json", "route_source_path": "route.json",
            "crosswalk_source_path": "crosswalk.json", "native_map_name": "TownTest",
            "official_head_id": "17", "ego_approach_id": "north",
            "facing_relation": True, "arrow_movement": "left",
            "ego_route_xy": [[0,-8],[0,0],[-8,0]],
            "intersection_polygon_xy": [[-3,-3],[3,-3],[3,3],[-3,3]],
            "adjacent_crosswalk_polygon_xy": [[3,-3],[6,-3],[6,3],[3,3]]}
        self.site_path = self.root / "site.json"

    def build(self, suffix, *, users=None, movement="left", concurrent=None):
        self.site["case_id"] = ASSIGNMENT + "__" + suffix
        self.site_path.write_text(json.dumps(self.site) + "\n")
        concurrent = concurrent or []
        def step(i):
            lit = i != 1
            aspect = {"frame": 100+i, "elapsed_seconds": i/20,
                "head_id": "17", "facing_approach_id": "north",
                "arrow_color": "yellow", "arrow_direction": "left", "arrow_lit": lit,
                "source_kind": "display_sensor", "source_id": "head-camera-17",
                "native_head_state": "Yellow", "concurrent_indications": concurrent}
            event = {"frame": 100+i, "official_head_id": "17",
                "facing_approach_id": "north", "arrow_movement": "left",
                "lit_aspects": ["flashing_yellow_turn_arrow"] if lit else [],
                "concurrent_indications": concurrent,
                "ego_movement": movement,
                "concurrently_permitted_movement": movement if concurrent else None,
                "ego_xy": [[0,-8],[0,0],[-8,0]][i],
                "other_users": users or []}
            return aspect, event
        capture_pair(self.site, self.root, step, frames=3, diagnostic=True)
        return finalize_saved(self.site_path, self.root, self.site["case_id"],
                              diagnostic=True)

    def test_exact_crosswalk_and_concurrent_variants(self):
        user = {"id": "p1", "kind": "pedestrian", "xy": [4,0],
                "lawful_presence_source": "reviewed-crossing-log"}
        result = self.build("arrow_ped_crosswalk", users=[user])
        self.assertIn(["pedestrian", "adjacent_crosswalk"],
                      result["observed_participant_regions"])
        self.assertEqual(result["frame_count"], 3)
        self.assertFalse(result["physical_acceptance"])
        self.assertIsNone(result["right_of_way_verdict"])

    def test_exact_concurrent_movement_requires_observed_indication(self):
        result = self.build("arrow_concurrent_movement", movement="straight",
                            concurrent=["straight_green"])
        self.assertTrue(result["event_aspect_join"])

    def test_wrong_region_rejected(self):
        user = {"id": "p1", "kind": "pedestrian", "xy": [0,0],
                "lawful_presence_source": "reviewed-crossing-log"}
        with self.assertRaisesRegex(ValueError, "participant and region"):
            self.build("arrow_ped_crosswalk", users=[user])

    def test_tampered_event_rejected_against_sealed_receipt(self):
        self.build("arrow_clear")
        path = self.root / "arrow-events-original.json"
        rows = json.loads(path.read_text())
        rows[1]["ego_xy"] = [50, 50]
        path.write_text(json.dumps(rows) + "\n")
        with self.assertRaisesRegex(ValueError, "event source hash mismatch"):
            finalize_saved(self.site_path, self.root, self.site["case_id"],
                           diagnostic=True)

    def test_original_mode_rejects_diagnostic_source(self):
        self.build("arrow_clear")
        with self.assertRaisesRegex(ValueError, "original reviewed Native arrow site"):
            finalize_saved(self.site_path, self.root, self.site["case_id"])


if __name__ == "__main__":
    unittest.main()
