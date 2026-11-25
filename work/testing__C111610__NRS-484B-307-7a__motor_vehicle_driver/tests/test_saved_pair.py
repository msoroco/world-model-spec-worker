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
        self._attempts = 0

    def attempt(self, suffix, users, *, movement="left", concurrent=None):
        self._attempts += 1
        root = self.root / f"{self._attempts}-{suffix}"
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
        if suffix == "arrow_concurrent_movement":
            route = root / "concurrent_route.json"
            site["concurrent_route_xy"] = [[0, -8], [0, 0], [0, 8]]
            route.write_text(json.dumps({"route_xy": site["concurrent_route_xy"]}) + "\n")
            site["concurrent_route_source_path"] = route.name
            refs.append({"path": route.name,
                         "sha256": hashlib.sha256(route.read_bytes()).hexdigest()})
        site_path = root / "site.json"
        site_path.write_text(json.dumps(site) + "\n")
        indications = [] if concurrent is None else list(concurrent)
        def sample(i):
            lit = i != 1
            aspect = {"frame": 100 + i, "elapsed_seconds": i / 20,
                      "head_id": "17", "facing_approach_id": "north",
                      "arrow_color": "yellow", "arrow_direction": "left",
                      "arrow_lit": lit, "source_kind": "display_sensor",
                      "source_id": "head-camera-17", "native_head_state": "Yellow",
                      "concurrent_indications": indications}
            event = {"frame": 100 + i, "official_head_id": "17",
                     "facing_approach_id": "north", "arrow_movement": "left",
                     "lit_aspects": ["flashing_yellow_turn_arrow"] if lit else [],
                     "concurrent_indications": indications, "ego_movement": movement,
                     "concurrently_permitted_movement": movement if indications else None,
                     "concurrent_permission_source": "reviewed-concurrent-controller" if indications else None,
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

    def test_every_other_selected_comparison_replays_sealed_sources(self):
        participants = (
            ("pedestrian_intersection", "arrow_ped_intersection", "pedestrian"),
            ("other_traffic_intersection", "arrow_vehicle_intersection", "motor_vehicle"),
        )
        for comparison, suffix, kind in participants:
            with self.subTest(comparison=comparison):
                left = self.attempt("arrow_clear", [])
                right = self.attempt(suffix, [{"id": "u1", "kind": kind,
                    "xy": [0, 0], "lawful_presence_source": "reviewed-presence-log"}])
                result = audit_saved_pair(comparison, *left, *right,
                                          diagnostic=True)
                self.assertEqual(result["comparison_id"], comparison)
                self.assertFalse(result["physical_acceptance"])

    def test_concurrent_movement_comparison_replays_display_inventory(self):
        left = self.attempt("arrow_clear", [])
        right = self.attempt("arrow_concurrent_movement", [],
                             movement="straight", concurrent=["straight_green"])
        result = audit_saved_pair("concurrent_indication", *left, *right,
                                  diagnostic=True)
        self.assertEqual(result["comparison_id"], "concurrent_indication")
        self.assertFalse(result["physical_acceptance"])
        self.assertNotEqual(result["source_hashes"]["left"]["site"],
                            result["source_hashes"]["right"]["site"])
