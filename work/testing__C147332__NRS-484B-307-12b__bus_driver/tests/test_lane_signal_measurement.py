import sys
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from lane_signal_measurement import measure
from bus_route import route
from source_review import validate
from analysis import build_report
from native_construction import candidate_opendrive, check_road, check_scene
from native_driver import control_request, spawn_scene
from native_capture import _footprint, _retain_review


def sample(frame, lateral, longitudinal, symbol="red_x"):
    t = frame / 20
    common = {"frame": frame, "elapsed_seconds": t, "source_sha256": "a" * 64}
    body = {**common, "bus_footprint": [[longitudinal - 5, lateral - 1],
                                          [longitudinal + 5, lateral - 1],
                                          [longitudinal + 5, lateral + 1],
                                          [longitudinal - 5, lateral + 1]]}
    signal = {**common, "governed_lane_id": "red_lane", "lane_lateral_bounds_m": [-3.6, 0],
              "symbol": symbol, "faces_bus": True, "official_device_source_sha256": "b" * 64}
    return {"frame": frame, "elapsed_seconds": t, "body": body,
            "lane_signal": signal, "camera_frame": dict(common)}


class RedXLaneMeasurement(unittest.TestCase):
    def test_native_footprint_uses_observed_world_vertices(self):
        class Point:
            def __init__(self, x, y): self.x, self.y = x, y
        class Bounds:
            def get_world_vertices(self, transform):
                return [Point(1, -7), Point(8, -7), Point(8, -3), Point(1, -3)]
        class Bus:
            bounding_box = Bounds()
            def get_transform(self): return object()
        self.assertEqual(_footprint(Bus()), [[1, -7], [8, -7], [8, -3], [1, -3]])

    def test_rotated_bus_retains_oriented_corners(self):
        class Point:
            def __init__(self, x, y): self.x, self.y = x, y
        class Bounds:
            def get_world_vertices(self, transform):
                corners = [Point(-2, 0), Point(0, -2), Point(2, 0), Point(0, 2)]
                return corners + corners
        class Bus:
            bounding_box = Bounds()
            def get_transform(self): return object()
        self.assertEqual(_footprint(Bus()), [[-2.0, 0.0], [0.0, -2.0],
                                              [2.0, 0.0], [0.0, 2.0]])

    def test_pitched_bus_uses_lower_four_body_corners(self):
        class Point:
            def __init__(self, x, y, z): self.x, self.y, self.z = x, y, z
        class Bounds:
            def get_world_vertices(self, transform):
                lower = [Point(-2, 0, 0.1), Point(0, -2, 0.2),
                         Point(2, 0, 0.3), Point(0, 2, 0.4)]
                upper = [Point(-3, -3, 2.1), Point(3, -3, 2.2),
                         Point(3, 3, 2.3), Point(-3, 3, 2.4)]
                return upper + lower
        class Bus:
            bounding_box = Bounds()
            def get_transform(self): return object()
        self.assertEqual(_footprint(Bus()), [[-2.0, 0.0], [0.0, -2.0],
                                              [2.0, 0.0], [0.0, 2.0]])

    def test_native_packet_retains_original_review_source_bytes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, attempt = root / "source", root / "attempt"
            source.mkdir(); attempt.mkdir()
            (source / "highway.txt").write_text("highway source")
            (source / "device.txt").write_text("device source")
            packet = {"highway": {"source_path": "highway.txt"},
                      "official_device": {"source_path": "device.txt"}}
            (source / "packet.json").write_text(json.dumps(packet))
            _retain_review(source / "packet.json", attempt)
            self.assertEqual((attempt / "device.txt").read_text(), "device source")
            with self.assertRaisesRegex(ValueError, "collides"):
                _retain_review(source / "packet.json", attempt)

    def test_controller_requests_smooth_lateral_entry_and_stationary_hold(self):
        scene = {"route": route("lateral_entry")}
        before = control_request(scene, x_m=30, y_m=-5.4, yaw_deg=0, speed_mps=4)
        middle = control_request(scene, x_m=45, y_m=-5.4, yaw_deg=0, speed_mps=4)
        after = control_request(scene, x_m=60, y_m=-1.8, yaw_deg=0, speed_mps=4)
        self.assertEqual(before["target_lateral_m"], -5.4)
        self.assertGreater(middle["target_lateral_m"], -5.4)
        self.assertLess(middle["target_lateral_m"], -1.8)
        self.assertAlmostEqual(after["target_lateral_m"], -1.8)
        hold = control_request({"route": route("red_lane_stand")},
                               x_m=8, y_m=-1.8, yaw_deg=0, speed_mps=0)
        self.assertEqual((hold["throttle"], hold["brake"]), (0.0, 1.0))

    def test_native_spawn_requests_exact_bus_and_head(self):
        class Point:
            def __init__(self, **kwargs): self.__dict__.update(kwargs)
        class FakeCarla:
            Location = Point
            Rotation = Point
            class Transform:
                def __init__(self, location, rotation):
                    self.location, self.rotation = location, rotation
        class Actor:
            def __init__(self):
                self.bounding_box = Point(extent=Point(x=3.4, y=1.25))
                self.destroyed = False
            def destroy(self): self.destroyed = True
        class Library:
            def find(self, identifier):
                if identifier not in ("vehicle.mitsubishi.fusorosa", "fixture.red_x_asset"):
                    raise ValueError("unavailable exact blueprint")
                return identifier
        class World:
            def __init__(self): self.spawns = []
            def get_blueprint_library(self): return Library()
            def spawn_actor(self, blueprint, transform):
                actor = Actor()
                self.spawns.append((blueprint, transform, actor))
                return actor
        world = World()
        scene = {"bus_blueprint_id": "vehicle.mitsubishi.fusorosa",
                 "route": route("lateral_entry"),
                 "signal": {"longitudinal_m": 50.0, "lateral_m": -1.8, "height_m": 6.0}}
        bus, head = spawn_scene(world, scene, FakeCarla,
                                {"native_asset_blueprint_id": "fixture.red_x_asset"})
        self.assertEqual([s[0] for s in world.spawns],
                         ["fixture.red_x_asset", "vehicle.mitsubishi.fusorosa"])
        self.assertEqual(world.spawns[0][1].location.y, -1.8)
        self.assertEqual(world.spawns[1][1].location.y, -5.4)
        self.assertIs(bus, world.spawns[1][2])
        self.assertIs(head, world.spawns[0][2])

    def test_candidate_one_way_map_and_signal_geometry(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "road.xodr"
            path.write_text(candidate_opendrive())
            road = check_road(path)
            self.assertEqual(road["lane_ids"], [-1, -2])
            for kind in ("adjacent_travel", "lateral_entry", "red_lane_stand", "red_lane_drive"):
                scene = {"assignment_id": "testing__C147332__NRS-484B-307-12b__bus_driver",
                         "case_id": "testing__C147332__NRS-484B-307-12b__bus_driver__" + kind,
                         "bus_blueprint_id": "vehicle.mitsubishi.fusorosa",
                         "route": route(kind), "map_source_sha256": road["road_sha256"],
                         "signal": {"display": "red_x", "governed_lane_id": "red_lane",
                                    "longitudinal_m": 50.0, "lateral_m": -1.8, "height_m": 6.0}}
                self.assertTrue(check_scene(scene, path)["bus_route_target_checked"])
                scene["signal"]["lateral_m"] = -5.4
                with self.assertRaisesRegex(ValueError, "above governed lane"):
                    check_scene(scene, path)
    def test_all_four_routes_construct_distinct_targets(self):
        routes = {kind: route(kind) for kind in
                  ("adjacent_travel", "lateral_entry", "red_lane_stand", "red_lane_drive")}
        self.assertEqual(routes["adjacent_travel"]["waypoint_centers_m"][-1][1], -5.4)
        self.assertEqual(routes["lateral_entry"]["waypoint_centers_m"][-1][1], -1.8)
        self.assertEqual(len(set(map(tuple, routes["red_lane_stand"]["waypoint_centers_m"]))), 1)
        self.assertGreater(len(set(map(tuple, routes["red_lane_drive"]["waypoint_centers_m"]))), 1)

    def test_adjacent_lane_has_no_entry_or_driving(self):
        result = measure([sample(1, -5.4, 0), sample(2, -5.4, 3)])
        self.assertEqual(result["red_x_entry_frames"], [])
        self.assertEqual(result["red_x_driving_frames"], [])

    def test_lateral_entry_detected_with_bus_footprint(self):
        result = measure([sample(1, -5.4, 0), sample(2, -3.9, 0)])
        self.assertEqual(result["red_x_entry_frames"], [2])
        self.assertEqual(result["red_x_driving_frames"], [])

    def test_in_lane_driving_distinct_from_stationary(self):
        result = measure([sample(1, -1.8, 0), sample(2, -1.8, 0), sample(3, -1.8, 3)])
        self.assertEqual(result["red_x_entry_frames"], [])
        self.assertEqual(result["red_x_driving_frames"], [3])

    def test_changed_signal_time_rejected(self):
        frames = [sample(1, -5.4, 0), sample(2, -3.9, 0)]
        frames[1]["lane_signal"]["elapsed_seconds"] = 9
        with self.assertRaisesRegex(ValueError, "join"):
            measure(frames)

    def test_missing_original_source_rejected(self):
        frames = [sample(1, -5.4, 0), sample(2, -3.9, 0)]
        frames[1]["camera_frame"]["source_sha256"] = ""
        with self.assertRaisesRegex(ValueError, "source hash"):
            measure(frames)

    def test_unreviewed_facing_rejected(self):
        frames = [sample(1, -5.4, 0), sample(2, -3.9, 0)]
        frames[1]["lane_signal"]["faces_bus"] = False
        with self.assertRaisesRegex(ValueError, "facing official"):
            measure(frames)

    def test_changed_lane_bounds_rejected(self):
        frames = [sample(1, -5.4, 0), sample(2, -3.9, 0)]
        frames[1]["lane_signal"]["lane_lateral_bounds_m"] = [-4, 0]
        with self.assertRaisesRegex(ValueError, "lane bounds changed"):
            measure(frames)

    def test_source_review_requires_original_bytes_and_lane_association(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "highway.txt").write_text("example retained highway source")
            (root / "device.txt").write_text("example retained device source")
            descriptor = lambda path: {"source_path": path,
                "source_sha256": hashlib.sha256((root / path).read_bytes()).hexdigest(),
                "reviewer": "fixture", "source_citation": "fixture citation"}
            packet = {"review_status": "reviewed",
                      "highway": {**descriptor("highway.txt"), "status": "public_highway_reviewed"},
                      "official_device": {**descriptor("device.txt"),
                         "device_kind": "official_overhead_lane_signal", "symbol": "red_x",
                         "faces_bus": True, "governed_lane_id": "red_lane",
                         "native_asset_blueprint_id": "fixture.red_x_asset"}}
            packet_path = root / "packet.json"
            packet_path.write_text(json.dumps(packet))
            self.assertEqual(validate(packet_path, source_root=root)["governed_lane_id"], "red_lane")
            packet["official_device"]["governed_lane_id"] = "adjacent_lane"
            packet_path.write_text(json.dumps(packet))
            with self.assertRaisesRegex(ValueError, "lane association"):
                validate(packet_path, source_root=root)
            packet["official_device"]["governed_lane_id"] = "red_lane"
            packet_path.write_text(json.dumps(packet))
            (root / "device.txt").write_text("tampered")
            with self.assertRaisesRegex(ValueError, "changed"):
                validate(packet_path, source_root=root)

    def test_saved_finalizer_binds_original_streams_and_device(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            originals = {"highway.txt": b"retained road source", "device.txt": b"retained official device",
                         "original-capture.bin": b"original sensor acquisition"}
            for name, data in originals.items():
                (root / name).write_bytes(data)
            sha = lambda name: hashlib.sha256((root / name).read_bytes()).hexdigest()
            descriptor = lambda name: {"source_path": name, "source_sha256": sha(name),
                                        "reviewer": "fixture", "source_citation": "fixture only"}
            packet = {"review_status": "reviewed",
                      "highway": {**descriptor("highway.txt"), "status": "public_highway_reviewed"},
                      "official_device": {**descriptor("device.txt"),
                          "device_kind": "official_overhead_lane_signal", "symbol": "red_x",
                          "faces_bus": True, "governed_lane_id": "red_lane",
                          "native_asset_blueprint_id": "fixture.red_x_asset"}}
            (root / "reviewed-context.json").write_text(json.dumps(packet))
            frames = [sample(1, -5.4, 0), sample(2, -3.9, 0)]
            channels = {"bus-body-history.jsonl": [f["body"] for f in frames],
                        "lane-signal-history.jsonl": [f["lane_signal"] for f in frames],
                        "camera-frame-map.jsonl": [f["camera_frame"] for f in frames]}
            acquisition = {name: sha(name) for name in originals}
            acquisition["reviewed-context.json"] = sha("reviewed-context.json")
            for name, rows in channels.items():
                for row in rows:
                    row["source_path"] = "original-capture.bin"
                    row["source_sha256"] = sha("original-capture.bin")
                    if name == "lane-signal-history.jsonl":
                        row["official_device_source_sha256"] = sha("device.txt")
                (root / name).write_text("".join(json.dumps(row) + "\n" for row in rows))
                acquisition[name] = sha(name)
            (root / "acquisition.json").write_text(json.dumps(acquisition))
            self.assertEqual(build_report(root)["measurements"]["red_x_bus_lane"]
                             ["red_x_entry_frames"], [2])
            (root / "lane-signal-history.jsonl").write_text("tampered\n")
            with self.assertRaisesRegex(ValueError, "changed"):
                build_report(root)


if __name__ == "__main__":
    unittest.main()
