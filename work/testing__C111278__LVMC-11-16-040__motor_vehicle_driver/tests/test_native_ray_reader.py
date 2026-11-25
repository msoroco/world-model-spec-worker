import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from native_ray_reader import NativeTrafficCensus, ReviewedRayReader, RayReadError
from sight_measurement import MeasurementError, evaluate


def location(x, y, z):
    return SimpleNamespace(x=x, y=y, z=z)


class World:
    def cast_ray(self, start, end):
        if end.x < -10:
            return [SimpleNamespace(location=location(-5, 0, 1.4), label="building")]
        return []


class Ego:
    def get_transform(self):
        return SimpleNamespace(location=location(0, -20, 0))


class RayReaderTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "arm-geometry.json"
        arms = ["north", "west", "east"]
        def corridor(x, y):
            return [{"station_m": i * 30.48 / 8,
                     "xyz": [x * i / 8, y * i / 8, 1.4]} for i in range(9)]
        self.source = {"source_kind": "arm_sight_geometry", "reviewer": "fixture reviewer",
                       "source_citation": "synthetic arm geometry only", "entering_arms": arms,
                       "arm_geometry": {
                           "north": {"sampled_extent_m": 31.0, "intersection_xyz": [0, 0, 1.4],
                                     "traffic_corridor_xyz": corridor(0, 31)},
                           "west": {"sampled_extent_m": 31.0, "intersection_xyz": [-1, 0, 1.4],
                                    "traffic_corridor_xyz": corridor(-31, 0)},
                           "east": {"sampled_extent_m": 31.0, "intersection_xyz": [1, 0, 1.4],
                                    "traffic_corridor_xyz": corridor(31, 0)}}}
        raw = json.dumps(self.source, sort_keys=True).encode()
        self.path.write_bytes(raw)
        self.site = {"entering_arms": arms,
                     "arm_sight_geometry_source_sha256": hashlib.sha256(raw).hexdigest()}

    @staticmethod
    def census(frame, snapshot, arm):
        source = {"frame": frame, "arm": arm, "actors": [],
                  "source_kind": "original_native_actor_census"}
        digest = hashlib.sha256(json.dumps(source, sort_keys=True,
                                        separators=(",", ":")).encode()).hexdigest()
        return {**source, "source_sha256": digest}

    def test_original_rays_all_arms_and_hit_trace(self):
        reader = ReviewedRayReader(self.site, self.path, World(), self.census, location)
        result = reader(7, SimpleNamespace(frame=7), Ego(), self.site["entering_arms"])
        self.assertEqual(set(result), set(self.site["entering_arms"]))
        self.assertEqual(result["west"]["traffic_view"], "blocked")
        self.assertEqual(result["north"]["traffic_view"], "clear")
        self.assertEqual(result["west"]["intersection_view"], "clear")
        self.assertTrue(result["west"]["ray_frame_source_sha256"])
        self.assertEqual(result["west"]["observer_convention"],
                         "ego_reference_1.4m_arm_rays")

    def test_tampered_geometry_and_missing_census_rejected(self):
        self.path.write_text("{}")
        with self.assertRaisesRegex(RayReadError, "hash differs"):
            ReviewedRayReader(self.site, self.path, World(), self.census, location)
        raw = json.dumps(self.source, sort_keys=True).encode()
        self.path.write_bytes(raw)
        reader = ReviewedRayReader(self.site, self.path, World(), lambda *args: {}, location)
        with self.assertRaisesRegex(RayReadError, "census missing"):
            reader(7, SimpleNamespace(frame=7), Ego(), self.site["entering_arms"])

    def test_missing_arm_and_frame_mismatch_rejected(self):
        reader = ReviewedRayReader(self.site, self.path, World(), self.census, location)
        with self.assertRaisesRegex(RayReadError, "inventory differs"):
            reader(7, SimpleNamespace(frame=7), Ego(), ["north", "west"])
        with self.assertRaisesRegex(RayReadError, "frame differs"):
            reader(7, SimpleNamespace(frame=8), Ego(), self.site["entering_arms"])

    def test_100_foot_corridor_gap_rejected(self):
        self.source["arm_geometry"]["west"]["traffic_corridor_xyz"] = [
            {"station_m": 0, "xyz": [0, 0, 1.4]},
            {"station_m": 30.48, "xyz": [-31, 0, 1.4]}]
        raw = json.dumps(self.source, sort_keys=True).encode()
        self.path.write_bytes(raw)
        self.site["arm_sight_geometry_source_sha256"] = hashlib.sha256(raw).hexdigest()
        with self.assertRaisesRegex(RayReadError, "sampling gap"):
            ReviewedRayReader(self.site, self.path, World(), self.census, location)

    def test_observed_traffic_body_is_not_its_own_occluder(self):
        class TrafficWorld:
            def cast_ray(self, start, end):
                return [SimpleNamespace(location=location(0, 18, 1.4),
                                        label="vehicle")] if end.y >= 18 else []
        def census(frame, snapshot, arm):
            bbox = [[x, y, z] for x in (-0.5, 0.5)
                    for y in (18, 20) for z in (0.5, 2.0)]
            actors = [{"id": 17, "xyz": [0, 19, 1.4], "bbox_xyz": bbox}] if arm == "north" else []
            source = {"frame": frame, "arm": arm, "actors": actors,
                      "source_kind": "original_native_actor_census"}
            digest = hashlib.sha256(json.dumps(source, sort_keys=True,
                                            separators=(",", ":")).encode()).hexdigest()
            return {**source, "source_sha256": digest}
        reader = ReviewedRayReader(self.site, self.path, TrafficWorld(), census, location)
        result = reader(7, SimpleNamespace(frame=7), Ego(), self.site["entering_arms"])
        self.assertEqual(result["north"]["traffic_view"], "clear")
        self.assertEqual(result["north"]["traffic_actor_ids"], ["17"])

    def test_original_native_actor_census_uses_reviewed_arm_polygons(self):
        geometry = {"north": {"traffic_arm_polygon_xy": [[-2, 2], [2, 2], [2, 35], [-2, 35]]},
                    "west": {"traffic_arm_polygon_xy": [[-35, -2], [-2, -2], [-2, 2], [-35, 2]]},
                    "east": {"traffic_arm_polygon_xy": [[2, -2], [35, -2], [35, 2], [2, 2]]}}
        def actor(identifier, kind, x, y):
            vertices = [location(x + dx, y + dy, dz)
                        for dx in (-0.5, 0.5) for dy in (-1, 1) for dz in (0, 2)]
            return SimpleNamespace(id=identifier, type_id=kind, is_alive=True,
                                   bounding_box=SimpleNamespace(
                                       get_world_vertices=lambda transform: vertices),
                                   get_transform=lambda: SimpleNamespace(location=location(x, y, 0)))
        actors = [actor(1, "vehicle.ego", 0, 12), actor(17, "vehicle.car", 0, 15),
                  actor(18, "walker.pedestrian", -15, 0), actor(19, "static.prop", 12, 0)]
        world = SimpleNamespace(get_actors=lambda: actors)
        census = NativeTrafficCensus(world, geometry, ego_id=1)
        north = census(9, SimpleNamespace(frame=9), "north")
        west = census(9, SimpleNamespace(frame=9), "west")
        self.assertEqual([a["id"] for a in north["actors"]], ["17"])
        self.assertEqual([a["id"] for a in west["actors"]], ["18"])
        self.assertEqual(len(north["source_sha256"]), 64)
        with self.assertRaisesRegex(RayReadError, "frame or arm"):
            census(9, SimpleNamespace(frame=10), "north")

    def test_saved_measurement_rechecks_ray_and_census_seals(self):
        reader = ReviewedRayReader(self.site, self.path, World(), self.census, location)
        arms = self.site["entering_arms"]
        rays0 = reader(7, SimpleNamespace(frame=7), Ego(), arms)
        rays1 = reader(8, SimpleNamespace(frame=8), Ego(), arms)
        packet = {"case_id": "fixture", "map_hash": "a" * 64,
                  "site_source_sha256": "a" * 64, "boundary_source_sha256": "a" * 64,
                  "through_source_sha256": "a" * 64, "control_source_sha256": "a" * 64,
                  "frame_source_sha256": "a" * 64, "ray_source_sha256": "a" * 64,
                  "speed_source_sha256": "a" * 64, "entering_arms": arms,
                  "frames": [
                      {"frame": 7, "time_s": .35, "approach_distance_m": 30.48,
                       "ego_speed_mps": 6.7, "traversing_intersection": False, "rays": rays0},
                      {"frame": 8, "time_s": .4, "approach_distance_m": 0,
                       "ego_speed_mps": 6.7, "traversing_intersection": False, "rays": rays1},
                      {"frame": 9, "time_s": .45, "approach_distance_m": -1,
                       "ego_speed_mps": 6.7, "traversing_intersection": True, "rays": {}}]}
        self.assertFalse(evaluate(packet)["all_views_clear"])
        packet["frames"][0]["rays"]["west"]["ray_hit_trace"]["traffic"][0]["hits"] = [
            {"label": "invented", "xyz": [0, 0, 0], "distance_m": 1}]
        with self.assertRaisesRegex(MeasurementError, "trace hash mismatch"):
            evaluate(packet)


if __name__ == "__main__":
    unittest.main()
