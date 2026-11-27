"""Exercise worker-owned Native calls without importing or launching CARLA."""

import hashlib
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import carla_yield_operator as operator
from native_capture import _validate_row
from yield_scene_construction import construct
from yield_view_measurement import ASSIGNMENT


class Box:
    def get_world_vertices(self, transform):
        x, y = transform.location.x, transform.location.y
        return [SimpleNamespace(x=x+dx, y=y+dy, z=z) for z in (0, 1)
                for dx, dy in ((-1, -1), (1, -1), (1, 1), (-1, 1))]


class Actor:
    def __init__(self, world, actor_id, kind, transform):
        self.world, self.id, self.type_id, self.transform = world, actor_id, kind, transform
        self.bounding_box = Box()
        self.control = None
        self.stopped = False

    def get_transform(self): return self.transform
    def get_velocity(self): return SimpleNamespace(x=2.0, y=0.0, z=0.0)
    def apply_control(self, control): self.control = control
    def listen(self, callback): self.callback = callback
    def stop(self): self.stopped = True
    def destroy(self): self.world.actors.pop(self.id, None)


class Blueprint:
    def __init__(self, kind): self.id, self.attributes = kind, {}
    def set_attribute(self, name, value): self.attributes[name] = value


class World:
    def __init__(self, source):
        self.source, self.actors, self.next_id, self.created = source, {}, 10, []
        self.landmarks = []

    def get_blueprint_library(self): return SimpleNamespace(find=lambda kind: Blueprint(kind))
    def get_map(self): return SimpleNamespace(to_opendrive=lambda: self.source,
                                               get_all_landmarks=lambda: self.landmarks)
    def get_actors(self): return list(self.actors.values())
    def get_actor(self, actor_id): return self.actors.get(actor_id)
    def spawn_actor(self, blueprint, transform, **kwargs):
        self.next_id += 1
        actor = Actor(self, self.next_id, blueprint.id, transform)
        self.actors[actor.id] = actor
        self.created.append(actor)
        return actor
    def cast_ray(self, origin, target):
        through = next((actor for actor in self.actors.values()
                        if actor.type_id == "vehicle.through"), None)
        return [SimpleNamespace(actor_id=through.id)] if through else []


class Carla:
    Location = lambda **kwargs: SimpleNamespace(**kwargs)
    Rotation = lambda **kwargs: SimpleNamespace(**kwargs)
    Transform = lambda location, rotation: SimpleNamespace(location=location, rotation=rotation)
    VehicleControl = lambda **kwargs: SimpleNamespace(**kwargs)


class WorkerOperatorTests(unittest.TestCase):
    def site(self):
        source = "reviewed OpenDRIVE fixture"
        digest = hashlib.sha256(source.encode()).hexdigest()
        p = lambda x, y: {"x": x, "y": y, "z": 0, "yaw": 0}
        case = ASSIGNMENT + "__yield_slow_hazard"
        return source, case, {
            "assignment_id": ASSIGNMENT, "cell_id": "C158190",
            "intersection_id": "reviewed-fixture", "review_status": "reviewed",
            "source_kind": "original_site_survey", "approved_control_variant": "yield_sign",
            **{key: digest for key in ("map_source_sha256", "ego_route_source_sha256",
               "yield_sign_survey_sha256", "marking_survey_sha256", "view_ray_survey_sha256",
               "through_highway_survey_sha256")},
            "police_control_active": False, "traffic_signal_control_active": False,
            "stop_line_present": False, "near_crosswalk_present": False,
            "sidewalk_derived_crosswalk_present": False,
            "yield_sign": {"blueprint_id": "static.prop.yield", "governed_approach_id": "approach-a",
                           "transform": p(0, 5)},
            "through_vehicle": {"route_source_id": "through-a"},
            "case_plans": {"yield_slow_hazard": {"ego_response": "slow",
                                                  "through_traffic_phase": "close",
                                                  "through_start_delay_s": 0.0}},
            "native_scene": {"ego": {"blueprint_id": "vehicle.ego", "transform": p(-10, 0)},
                             "through_vehicle": {"blueprint_id": "vehicle.through",
                                                 "transform": p(10, 0)},
                             "cameras": {view: {"attach_to": "ego", "transform": p(0, 0),
                                                "fov_deg": 80} for view in operator.VIEWS},
                             "intersection_polygon_xy_m": [[-2, -2], [2, -2], [2, 2], [-2, 2]],
                             "through_conflict_point_xy_m": [0, 0],
                             "approach_view_stations": [
                                 {"station_id": "far", "x": -8, "y": 0, "z": 1,
                                  "distance_to_intersection_m": 8, "reviewed_visible": True},
                                 {"station_id": "near", "x": -3, "y": 0, "z": 1,
                                  "distance_to_intersection_m": 3, "reviewed_visible": True}],
                             "brake_distance_m": 5, "slow_speed_mps": 2,
                             "through_speed_mps": 4}}

    def test_original_setup_900_frame_readback_and_reverse_release(self):
        source, case, site = self.site()
        world = World(source)
        adapter = operator.CarlaYieldOperator(world, site, case, Carla)
        with tempfile.TemporaryDirectory(dir=os.environ["SCENARIO_PIPELINE_OUTPUT_ROOT"]) as directory:
            packet = Path(directory) / "site.json"
            packet.write_text(json.dumps(site) + "\n")
            built = construct(adapter, packet, case)
        self.assertEqual(len(world.actors), 7)
        self.assertEqual(adapter.map_bytes(world), source.encode())
        self.assertEqual(adapter.read_original_context(site, case)["control"], "yield_sign")
        for index in range(900):
            adapter.control_frame(case, index)
            row = adapter.read_original_frame(case, index, 1000 + index)
            _validate_row(row, index, 1000 + index, site, case)
        self.assertIsNotNone(adapter.ego.control)
        self.assertIsNotNone(adapter.through.control)
        sensors = list(adapter.cameras.values())
        adapter.destroy(built["through_vehicle_actor_id"])
        self.assertTrue(all(sensor.stopped for sensor in sensors))
        self.assertEqual(len(world.actors), 1)
        adapter.destroy(built["yield_sign_actor_id"])
        self.assertEqual(world.actors, {})

    def test_camera_frame_join_and_missing_scene_rejected(self):
        source, case, site = self.site()
        with self.assertRaisesRegex(ValueError, "reviewed Native scene"):
            operator.validate_scene({})
        adapter = operator.CarlaYieldOperator(World(source), site, case, Carla)
        with patch.dict(operator.SIZES, {"overview": (2, 2)}):
            inbox = operator.queue.Queue()
            adapter.inboxes["overview"] = inbox
            inbox.put(SimpleNamespace(frame=7, width=2, height=2,
                                      raw_data=bytes((0, 0, 255, 255)) * 4))
            self.assertEqual(len(adapter.camera_rgb24("overview", 7)), 12)
            inbox.put(SimpleNamespace(frame=8, width=2, height=2,
                                      raw_data=bytes((0, 0, 255, 255)) * 4))
            with self.assertRaisesRegex(ValueError, "frame join"):
                adapter.camera_rgb24("overview", 9)

    def test_existing_map_stop_landmark_rejects_yield_variant(self):
        source, case, site = self.site()
        world = World(source)
        world.landmarks.append(SimpleNamespace(type="206", transform=SimpleNamespace(
            location=SimpleNamespace(x=0, y=5))))
        adapter = operator.CarlaYieldOperator(world, site, case, Carla)
        with tempfile.TemporaryDirectory(dir=os.environ["SCENARIO_PIPELINE_OUTPUT_ROOT"]) as directory:
            packet = Path(directory) / "site.json"
            packet.write_text(json.dumps(site) + "\n")
            with self.assertRaisesRegex(ValueError, "active stop sign"):
                construct(adapter, packet, case)
        self.assertEqual(world.actors, {})


if __name__ == "__main__":
    unittest.main()
