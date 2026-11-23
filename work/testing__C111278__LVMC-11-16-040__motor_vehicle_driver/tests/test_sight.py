import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sight_construction import CASES, ConstructionError, spawn_occluder, validate_site
from sight_measurement import MeasurementError, compare, evaluate

SHA = "a" * 64


def site(case="blocked_at"):
    c = CASES[case]
    return dict(jurisdiction="Las Vegas municipal", jurisdiction_source_sha256=SHA,
                road_kind="street", road_kind_source_sha256=SHA,
                entering_arms=["north", "west", "east"], entering_arms_source_sha256=SHA,
                ego_road_through=c.through, ego_road_through_source_sha256=SHA,
                traffic_controlled_intersection=c.controlled,
                traffic_controlled_intersection_source_sha256=SHA,
                boundary_source_sha256=SHA, map_hash=SHA,
                ego_route_xy=[[0, -40], [0, 0], [0, 15]],
                occluder_sites={"west_building": {"source_sha256": SHA,
                    "blueprint_id": "static.prop.test", "transform": {"x": -5, "y": 2},
                    "affected_arm": "west"}})


def measurement(blocked=True):
    def frame(n, distance, crossing=False):
        rays = {arm: dict(observer_convention="lane_waypoint_1.4m_bbox_9",
                          sampled_extent_m=31, intersection_view="clear",
                          traffic_view="blocked" if blocked and arm == "west" else "clear",
                          ray_frame_source_sha256=SHA)
                for arm in ("north", "west", "east")}
        return dict(frame=n, time_s=n/20, approach_distance_m=distance,
                    ego_speed_mps=6.7, traversing_intersection=crossing, rays=rays)
    return dict(case_id="blocked_at", map_hash=SHA, site_source_sha256=SHA,
                boundary_source_sha256=SHA, through_source_sha256=SHA,
                control_source_sha256=SHA, entering_arms=["north", "west", "east"],
                frames=[frame(10, 30.48), frame(11, 0), frame(12, -1, True)],
                frame_source_sha256=SHA, ray_source_sha256=SHA, speed_source_sha256=SHA,
                through_designation=False, traffic_controlled=False)


class Actor:
    is_alive = True
    def destroy(self): self.is_alive = False


class World:
    def __init__(self): self.calls = []
    def get_blueprint_library(self): return self
    def find(self, blueprint): self.calls.append(("find", blueprint)); return blueprint
    def try_spawn_actor(self, blueprint, transform):
        self.calls.append(("spawn", blueprint, transform)); return Actor()


class SightTests(unittest.TestCase):
    def test_cases_constructible_and_exception_source_gated(self):
        for name, case in CASES.items():
            with self.subTest(name=name):
                validate_site(site(name), case)
        p = site("through_blocked"); p["ego_road_through_source_sha256"] = ""
        with self.assertRaises(ConstructionError): validate_site(p, CASES["through_blocked"])
        p = site(); p["entering_arms"] = ["north", "west"]
        with self.assertRaises(ConstructionError): validate_site(p, CASES["blocked_at"])

    def test_occluder_is_spawned_and_clear_case_is_not(self):
        w = World(); actor = spawn_occluder(w, site(), CASES["blocked_at"])
        self.assertTrue(actor.is_alive)
        self.assertEqual(w.calls[-1], ("spawn", "static.prop.test", {"x": -5, "y": 2}))
        w = World(); self.assertIsNone(spawn_occluder(w, site("clear_at"), CASES["clear_at"]))
        self.assertEqual(w.calls, [])

    def test_measurement_and_missing_arm_rejection(self):
        self.assertFalse(evaluate(measurement())["all_views_clear"])
        self.assertTrue(evaluate(measurement(False))["all_views_clear"])
        p = measurement(); del p["frames"][0]["rays"]["east"]
        with self.assertRaises(MeasurementError): evaluate(p)
        p = measurement(); p["frames"][0]["rays"]["east"]["sampled_extent_m"] = 29
        with self.assertRaises(MeasurementError): evaluate(p)

    def test_temporal_and_boundary_rejection(self):
        p = measurement(); p["frames"][1]["frame"] = 14
        with self.assertRaises(MeasurementError): evaluate(p)
        p = measurement(); p["frames"][0]["approach_distance_m"] = 20
        with self.assertRaises(MeasurementError): evaluate(p)

    def test_independent_comparison(self):
        a = evaluate(measurement()); b = evaluate(measurement(False))
        compare(a, b, {"sight"})
        with self.assertRaises(MeasurementError): compare(a, b, {"traversal_speed"})
        b["map_hash"] = "b" * 64
        with self.assertRaises(MeasurementError): compare(a, b, {"sight"})


if __name__ == "__main__": unittest.main()
