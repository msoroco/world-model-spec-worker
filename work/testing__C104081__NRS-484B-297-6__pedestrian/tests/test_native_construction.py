import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from native_construction import construct_native, load_site_survey


class FakeNativeAdapter:
    def __init__(self):
        self.calls = []
        self.fail_route = False

    def spawn_obstacle(self, shape, transform):
        self.calls.append(("obstacle", shape.name))
        return "obstacle-" + shape.name

    def verify_existing_gap(self, shape, transform):
        self.calls.append(("verified_gap", shape.name))

    def spawn_pedestrian(self, point, transform):
        self.calls.append(("pedestrian", point))
        return "walker"

    def set_pedestrian_route(self, walker, route, transform):
        self.calls.append(("route", len(route)))
        if self.fail_route:
            raise RuntimeError("route controller failed")

    def readback(self, walker, owned, map_id):
        self.calls.append(("readback", map_id))
        return {"map_id": map_id, "walker_spawned": True,
                "obstacle_count": sum(h.startswith("obstacle-") for h in owned)}

    def destroy(self, handle):
        self.calls.append(("destroy", handle))


class NativeConstructionTests(unittest.TestCase):
    def setUp(self):
        self.plan = json.loads((ROOT / "case-plan.json").read_text())
        self.ids = {c["case_id"].split("__")[-1]: c["case_id"] for c in self.plan["cases"]}
        self.survey = {
            "source_kind": "original_native_map_survey", "cell_id": "C104081",
            "map_id": "surveyed-hill-road", "layout": "hill_crest",
            "surfaces": {key: {"surveyed": True} for key in
                         ("sidewalk", "intervening_area", "designated_bicycle_lane",
                          "immediately_adjacent_highway")},
            "local_to_world": {"x": 100.0, "y": 200.0, "yaw_degrees": 3.0},
            "observed_missing_sidewalk_intervals_local_m": [[20, 34.0]],
        }
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)

    def _construct(self, case_id, adapter):
        path = Path(self.temp.name) / "survey.json"
        raw = json.dumps(self.survey, sort_keys=True).encode()
        path.write_bytes(raw)
        return construct_native(self.plan, case_id, path, hashlib.sha256(raw).hexdigest(), adapter)

    def test_hashed_survey_required(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "survey.json"
            raw = json.dumps(self.survey, sort_keys=True).encode()
            path.write_bytes(raw)
            self.assertEqual(load_site_survey(path, hashlib.sha256(raw).hexdigest())["map_id"],
                             "surveyed-hill-road")
            with self.assertRaisesRegex(ValueError, "digest"):
                load_site_survey(path, "0" * 64)
            self.survey["source_kind"] = "synthetic_fixture"
            path.write_text(json.dumps(self.survey))
            with self.assertRaisesRegex(ValueError, "original"):
                load_site_survey(path, hashlib.sha256(path.read_bytes()).hexdigest())

    def test_blocked_area_spawns_two_physical_obstacles_and_walker(self):
        adapter = FakeNativeAdapter()
        result = self._construct(self.ids["blocked_intervening"], adapter)
        self.assertEqual([name for name, _ in adapter.calls[:3]],
                         ["obstacle", "obstacle", "pedestrian"])
        self.assertEqual(result["native_readback"]["obstacle_count"], 2)

    def test_opposite_route_spawns_from_opposite_side(self):
        adapter = FakeNativeAdapter()
        self._construct(self.ids["blocked_opposite"], adapter)
        self.assertEqual(next(value for name, value in adapter.calls if name == "pedestrian"),
                         (50, 5))

    def test_missing_surface_requires_observed_gap_and_no_fake_object(self):
        adapter = FakeNativeAdapter()
        self.survey["observed_missing_sidewalk_intervals_local_m"] = []
        with self.assertRaisesRegex(ValueError, "absent"):
            self._construct(self.ids["missing_sidewalk"], adapter)
        self.assertEqual(adapter.calls, [])
        self.survey["observed_missing_sidewalk_intervals_local_m"] = [[20, 34.0]]
        self._construct(self.ids["missing_sidewalk"], adapter)
        self.assertEqual(adapter.calls[0][0], "verified_gap")
        self.assertFalse(any(name == "obstacle" for name, _ in adapter.calls))

    def test_failed_route_releases_owned_handles_in_reverse(self):
        adapter = FakeNativeAdapter()
        adapter.fail_route = True
        with self.assertRaisesRegex(RuntimeError, "route controller"):
            self._construct(self.ids["blocked_intervening"], adapter)
        destroyed = [value for name, value in adapter.calls if name == "destroy"]
        self.assertEqual(destroyed, ["walker", "obstacle-intervening_barrier",
                                     "obstacle-impassable_sidewalk_section"])

    def test_incomplete_survey_rejected_before_spawning(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "survey.json"
            self.survey["surfaces"].pop("designated_bicycle_lane")
            path.write_text(json.dumps(self.survey))
            with self.assertRaisesRegex(ValueError, "required observed surface"):
                load_site_survey(path, hashlib.sha256(path.read_bytes()).hexdigest())


if __name__ == "__main__":
    unittest.main()
