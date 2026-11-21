import importlib.util
import json
import tempfile
import unittest
import sys
from pathlib import Path
from types import SimpleNamespace as NS


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / (name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


measure = load("crossing_measurements")
signs = load("stop_sign_control")
comparison = load("comparison_audit")


def body(x):
    return [[x, 1], [x, -1], [x - 2, 1], [x - 2, -1]]


class FakeSign:
    def __init__(self, valid):
        self.id, self.calls = 10, []
        def contains(point, transform):
            self.calls.append((point, transform))
            return valid
        self.trigger_volume = NS(contains=contains)

    def get_transform(self):
        return "native-sign-transform"


def site():
    return {"native_map_name": "TownX", "junction_id": 9,
            "highway_ids": {"ego": "a", "other": "b"},
            "crossing_source": "review/crossing", "median_opening_source": "review/median",
            "different_highways_source": "review/highways",
            "device_inventory_source": "review/devices",
            "sign_erection_source": "review/sign", "camera_plan_source": "review/cameras",
            "crossing_polygon_xy_m": [[0, -5], [10, -5], [10, 5], [0, 5]],
            "ego_approach": [-10, 0, 0, 0], "ego_entry": [2, 0, 0, 0],
            "other_approach": [5, -10, 0, 90], "other_entry": [5, 0, 0, 90]}


class FakeActors(list):
    def filter(self, pattern):
        assert pattern == "traffic.stop*"
        return self


class CrossingTests(unittest.TestCase):
    def fixture(self, root):
        context = {"native_map_id": "TownX", "intersection_id": 9,
                   "ego_highway_id": "highway-a", "other_highway_id": "highway-b",
                   "ego_road_id": 3, "other_road_id": 4,
                   "native_stop_sign_id": 10, "sign_governance_source": "native-trigger",
                   "stop_sign_video_source": "front-original", "intersection_polygon_source": "native-map-junction",
                   "stop_sign_erected": True, "stop_sign_governed_road_id": 3,
                   "intersection_polygon_xy_m": [[0, -5], [10, -5], [10, 5], [0, 5]]}
        (root / "junction_context.json").write_text(json.dumps(context))
        ego_x, other_x = [-20, -18, -10, 1], [-4, 1, 3, 5]
        rows = []
        for i in range(4):
            rows.append({"frame": 100+i, "time_s": 1+i*.05,
                         "native_stop_sign_id": 10,
                         "ego": {"intersection_id": 9, "road_id": 3,
                                 "distance_to_intersection_m": max(0, -ego_x[i]),
                                 "speed_mps": 3 if i != 2 else 0,
                                 "body_vertices_xy_m": body(ego_x[i])},
                         "other": {"intersection_id": 9, "road_id": 4,
                                   "distance_to_intersection_m": max(0, -other_x[i]),
                                   "speed_mps": 3, "body_vertices_xy_m": body(other_x[i])}})
        frames = [{"video_frame": i, "carla_frame": row["frame"], "time_s": row["time_s"]}
                  for i, row in enumerate(rows)]
        (root / "crossing_history.jsonl").write_text("".join(json.dumps(row)+"\n" for row in rows))
        (root / "video_frames.jsonl").write_text("".join(json.dumps(row)+"\n" for row in frames))

    def test_native_stop_trigger_selection(self):
        wrong, right = FakeSign(False), FakeSign(True)
        world = NS(get_actors=lambda: FakeActors([wrong, right]))
        waypoint = NS(transform=NS(location="ego-approach-point"))
        self.assertIs(signs.find_governing_stop_sign(world, waypoint), right)
        self.assertEqual(right.calls, [("ego-approach-point", "native-sign-transform")])
        with self.assertRaisesRegex(ValueError, "found 0"):
            signs.find_governing_stop_sign(NS(get_actors=lambda: FakeActors([wrong])), waypoint)

    def test_other_first_at_stop_sign_and_context_rejections(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.fixture(root)
            report = measure.analyze(root)
            self.assertTrue(report["other_entered_before_ego_observed"])
            self.assertTrue(report["ego_approaching_at_other_entry_observed"])
            self.assertIn("unresolved", report["official_device_exclusion_judgment"])
            context = json.loads((root / "junction_context.json").read_text())
            context["stop_sign_governed_road_id"] = 4
            (root / "junction_context.json").write_text(json.dumps(context))
            with self.assertRaisesRegex(ValueError, "governing stop sign"):
                measure.analyze(root)

    def test_stale_frame_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.fixture(root)
            frames = [json.loads(line) for line in (root / "video_frames.jsonl").read_text().splitlines()]
            frames[1]["carla_frame"] = 999
            (root / "video_frames.jsonl").write_text("".join(json.dumps(row)+"\n" for row in frames))
            with self.assertRaisesRegex(ValueError, "frame join"):
                measure.analyze(root)

    def test_site_geometry_rejects_wrong_direction_and_highway(self):
        packet = site()
        self.assertGreater(signs.validate_site(packet).area, 0)
        packet["ego_approach"][3] = 180
        with self.assertRaisesRegex(ValueError, "points away"):
            signs.validate_site(packet)
        packet = site()
        packet["highway_ids"]["other"] = "a"
        with self.assertRaisesRegex(ValueError, "Distinct sourced"):
            signs.validate_site(packet)

    def test_native_construction_and_cleanup(self):
        packet = site()
        transforms = {key: NS(location=key) for key in
                      ("ego_approach", "ego_entry", "other_approach", "other_entry")}
        waypoints = {
            "ego_approach": NS(road_id=3, transform=NS(location="ego-approach-point")),
            "other_approach": NS(road_id=4, transform=NS(location="other-approach-point")),
            "ego_entry": NS(road_id=3, is_junction=True, get_junction=lambda: NS(id=9)),
            "other_entry": NS(road_id=4, is_junction=True, get_junction=lambda: NS(id=9)),
        }
        sign = FakeSign(True)
        sign.trigger_volume = NS(contains=lambda point, transform:
                                 point == "ego-approach-point")
        actors = []
        def spawn(blueprint, transform):
            actor = NS(destroy=lambda: actors.remove(actor))
            actors.append(actor)
            return actor
        world = NS(get_map=lambda: NS(name="TownX", get_waypoint=lambda point, project_to_road:
                                      waypoints[point]),
                   get_actors=lambda: FakeActors([sign]), try_spawn_actor=spawn)
        with signs.construct_candidate(world, packet, transforms, "vehicle") as candidate:
            self.assertEqual(candidate["approach_road_ids"], {"ego": 3, "other": 4})
            self.assertEqual(len(actors), 2)
        self.assertEqual(actors, [])
        waypoints["other_entry"] = NS(road_id=4, is_junction=True,
                                        get_junction=lambda: NS(id=10))
        with self.assertRaisesRegex(ValueError, "selected Native junction"):
            with signs.construct_candidate(world, packet, transforms, "vehicle"):
                pass
        self.assertEqual(actors, [])

    def test_native_capture_row_keeps_body_and_live_road(self):
        polygon = site()["crossing_polygon_xy_m"]
        snapshot = NS(frame=101, timestamp=NS(elapsed_seconds=5.05))
        world_map = NS(get_waypoint=lambda location, project_to_road:
                       NS(road_id=3 if location == "ego" else 4, lane_id=1))
        def actor(actor_id, location, x):
            transform = NS(location=location)
            vertices = [NS(x=px, y=py) for px, py in body(x)]
            return NS(id=actor_id, get_transform=lambda: transform,
                      bounding_box=NS(get_world_vertices=lambda value: vertices),
                      get_velocity=lambda: NS(x=3, y=0, z=0))
        ego, other = actor(1, "ego", -10), actor(2, "other", 2)
        row = measure.capture_sample(snapshot, world_map, ego, other, NS(id=10), polygon, 9)
        self.assertEqual(row["ego"]["road_id"], 3)
        self.assertEqual(row["other"]["actor_id"], 2)
        self.assertEqual(len(row["other"]["body_vertices_xy_m"]), 4)
        with self.assertRaisesRegex(ValueError, "Distinct Native"):
            measure.capture_sample(snapshot, world_map, ego, ego, NS(id=10), polygon, 9)

    def test_independent_entry_order_comparison(self):
        with tempfile.TemporaryDirectory() as temp:
            first, second = Path(temp) / "first", Path(temp) / "second"
            first.mkdir()
            second.mkdir()
            self.fixture(first)
            self.fixture(second)
            rows = [json.loads(line) for line in (second / "crossing_history.jsonl").read_text().splitlines()]
            ego_bodies = [row["ego"]["body_vertices_xy_m"] for row in rows]
            other_bodies = [row["other"]["body_vertices_xy_m"] for row in rows]
            for row, ego_body, other_body in zip(rows, ego_bodies, other_bodies):
                row["ego"]["body_vertices_xy_m"] = other_body
                row["other"]["body_vertices_xy_m"] = ego_body
            (second / "crossing_history.jsonl").write_text("".join(json.dumps(row)+"\n" for row in rows))
            receipt = comparison.compare(first, second, expected_frames=4)
            self.assertFalse(receipt["physical_acceptance_claimed"])
            with self.assertRaisesRegex(ValueError, "Incomplete original"):
                comparison.compare(first, second)
            context = json.loads((second / "junction_context.json").read_text())
            context["native_stop_sign_id"] = 99
            (second / "junction_context.json").write_text(json.dumps(context))
            with self.assertRaises(ValueError):
                comparison.compare(first, second, expected_frames=4)


if __name__ == "__main__":
    unittest.main()
