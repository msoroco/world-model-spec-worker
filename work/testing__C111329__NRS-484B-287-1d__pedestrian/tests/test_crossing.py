import importlib.util
import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from native_crossing import construct_walker, crossing_plan
from saved_measurement import measure
from comparison_audit import audit


def site(authorized=False):
    return {"map_name": "test-map", "map_sha256": "a"*64, "survey_source": "measured-map-packet", "intersection_polygon": [[-1,-1],[11,-1],[11,11],[-1,11]], "corners": [[0,0],[10,0],[10,10],[0,10]], "devices": [{"id": "d1", "official_source": "agency-inventory", "instruction_source": "device-instruction", "pedestrian_governance": "diagonal" if authorized else "straight", "state": "permissive"}]}


class FakeWorld:
    def __init__(self, fail=False): self.fail, self.destroyed, self.path = fail, False, None
    def spawn_walker(self, bp, p): return {"id": 7, "bp": bp, "p": p}
    def drive_walker_route(self, actor, path):
        if self.fail: raise ValueError("route adapter failed")
        self.path = path
    def walker_id(self, actor): return actor["id"]
    def destroy_actor(self, actor): self.destroyed = True


class CrossingTests(unittest.TestCase):
    def test_independent_comparison_rejects_confounds_and_missing_sources(self):
        base = {"case_id": "a", "map_sha256": "m", "intersection_polygon": [[0,0]], "walker_blueprint_id": "walker.pedestrian.0001", "camera_contract_sha256": "c", "duration_frames": 900, "fps": 20, "original_measurement": {"walker_id": 7, "device_source_hashes": ["s"]}, "device_inventory_sha256": "d", "route_kind": "opposite", "authorization_observed": False}
        other = dict(base, case_id="b", authorization_observed=True)
        self.assertTrue(audit(base, other, "diagonal_device_authority")["passed"])
        with self.assertRaisesRegex(ValueError, "fixed condition"):
            audit(base, dict(other, map_sha256="different"), "diagonal_device_authority")
        with self.assertRaisesRegex(ValueError, "did not vary"):
            audit(base, dict(other, authorization_observed=False), "diagonal_device_authority")
        with self.assertRaisesRegex(ValueError, "source-bound"):
            audit(base, dict(other, original_measurement=None), "diagonal_device_authority")

    def test_adjacent_and_opposite_geometry(self):
        a = crossing_plan(site(), "adjacent", False)
        d = crossing_plan(site(True), "opposite", True)
        self.assertEqual(a["end"], (10,0))
        self.assertEqual(d["end"], (10,10))
        self.assertEqual(len(d["waypoints"]), 21)
        self.assertEqual(d["authorizing_device_ids"], ["d1"])

    def test_road_or_straight_signal_cannot_authorize_diagonal(self):
        with self.assertRaisesRegex(ValueError, "authorization"):
            crossing_plan(site(), "opposite", True)
        s = site(True); s["devices"][0]["official_source"] = None
        with self.assertRaisesRegex(ValueError, "authorization"):
            crossing_plan(s, "opposite", True)

    def test_native_command_and_cleanup(self):
        w = FakeWorld(); actor, p = construct_walker(w, site(), "adjacent", False, "walker.pedestrian.0001")
        self.assertEqual(actor["id"], 7); self.assertEqual(w.path[-1], (10,0))
        w = FakeWorld(True)
        with self.assertRaisesRegex(ValueError, "adapter"):
            construct_walker(w, site(), "adjacent", False, "walker.pedestrian.0001")
        self.assertTrue(w.destroyed)

    def test_original_measurement_and_missing_source_rejection(self):
        p = crossing_plan(site(True), "opposite", True)
        frames = [{"original_frame": i, "walker_id": 7, "walker_center_xy": [i*5,i*5]} for i in range(3)]
        dev = [{"original_frame": i, "source_sha256": "b"*64, "official_source": "agency", "pedestrian_governance": "diagonal", "state": "permissive"} for i in range(3)]
        out = measure(p, frames, dev)
        self.assertTrue(out["authorization_observed_during_inside"])
        self.assertEqual(out["observed_inside_frames"], 3)
        with self.assertRaisesRegex(ValueError, "incomplete"):
            measure(p, frames, dev[:-1])
        frames[1]["walker_id"] = 9
        with self.assertRaisesRegex(ValueError, "identity"):
            measure(p, frames, dev)


if __name__ == "__main__": unittest.main()
