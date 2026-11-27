import copy
import hashlib
import importlib.util
import json
import os
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("transit_road_scene", ROOT / "road_scene.py")
scene = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(scene)


def body(x, y):
    return [[x, y, 0], [x + 1, y, 0], [x + 1, y + 1, 0], [x, y + 1, 0]]


class RoadSceneTests(unittest.TestCase):
    def setUp(self):
        scratch = Path(os.environ["SCENARIO_PIPELINE_OUTPUT_ROOT"])
        scratch.mkdir(parents=True, exist_ok=True)
        self.tmp = tempfile.TemporaryDirectory(dir=scratch)
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / "map.xodr").write_text("<OpenDRIVE/>")
        self.site = {"format": "worker-transit-stop-site", "cell_id": "C394554",
                     "layout": "road", "control": "bus_stop",
                     "map_source": {"path": "map.xodr", "sha256": hashlib.sha256(b"<OpenDRIVE/>").hexdigest()},
                     "road": {"lane_source": "original waypoint", "road_id": 0},
                     "stop": {"actor_id": 30, "blueprint_id": "static.prop.busstop",
                              "position_m": [0, 6, 0], "position_source": "original actor transform"},
                     "bus": {"actor_id": 40, "blueprint_id": "vehicle.bus",
                             "position_m": [1, 4, 0], "body_vertices_m": body(0, 3),
                             "door_side_source": "original bus body and curb side",
                             "door_region_source": "original bus body proxy and reviewed image",
                             "door_region_m": {"x_min": 0, "x_max": 1, "y_min": 4,
                                               "y_max": 4.5}}}
        self.path = self.root / "transit-site.json"
        self.save()

    def save(self):
        self.path.write_text(json.dumps(self.site) + "\n")

    def sample(self, phase="waiting_at_stop"):
        return {"ego_class": "motor_vehicle", "pedestrian_class": "pedestrian",
                "ego_class_source": "original blueprint", "pedestrian_class_source": "original blueprint",
                "bus_actor_id": 40, "stop_actor_id": 30,
                "driver_control_source": "scripted driver log", "driver_observation_event": None,
                "ego_body_vertices_m": body(-5, 0), "pedestrian_body_vertices_m": body(0, 5),
                "bus_body_vertices_m": body(0, 3), "ego_speed_mps": 5,
                "ego_brake": 0, "passenger_phase": phase}

    def test_original_map_stop_and_bus_are_required(self):
        self.assertEqual(scene.load_site(self.path)["road"]["road_id"], 0)
        for branch, key, value, error in (("stop", "blueprint_id", "static.prop.trafficcone", "bus stop blueprint"),
                                          ("bus", "blueprint_id", "vehicle.car", "public bus"),
                                          ("bus", "door_region_source", None, "boarding-side")):
            bad = copy.deepcopy(self.site)
            bad[branch][key] = value
            self.site = bad
            self.save()
            with self.assertRaisesRegex(ValueError, error):
                scene.load_site(self.path)
            self.site = self.base_site()
        (self.root / "map.xodr").write_text("changed")
        with self.assertRaisesRegex(ValueError, "stale"):
            scene.load_site(self.path)

    def base_site(self):
        return {"format": "worker-transit-stop-site", "cell_id": "C394554",
                "layout": "road", "control": "bus_stop",
                "map_source": {"path": "map.xodr", "sha256": hashlib.sha256(b"<OpenDRIVE/>").hexdigest()},
                "road": {"lane_source": "original waypoint", "road_id": 0},
                "stop": {"actor_id": 30, "blueprint_id": "static.prop.busstop",
                         "position_m": [0, 6, 0], "position_source": "original actor transform"},
                "bus": {"actor_id": 40, "blueprint_id": "vehicle.bus",
                        "position_m": [1, 4, 0], "body_vertices_m": body(0, 3),
                        "door_side_source": "original bus body and curb side",
                        "door_region_source": "original bus body proxy and reviewed image",
                        "door_region_m": {"x_min": 0, "x_max": 1, "y_min": 4,
                                          "y_max": 4.5}}}

    def test_waiting_and_boarding_are_measured_without_legal_verdict(self):
        site = scene.load_site(self.path)
        waiting = scene.measure(site, self.sample())
        self.assertEqual(waiting["passenger_phase"], "waiting_at_stop")
        self.assertIsNone(waiting["legal_proper_caution_verdict"])
        active = self.sample("boarding_bus")
        active["pedestrian_body_vertices_m"] = body(0, 4.25)
        boarding = scene.measure(site, active)
        self.assertLess(boarding["pedestrian_bus_door_region_gap_m"],
                        waiting["pedestrian_bus_door_region_gap_m"])
        self.assertIsNone(boarding["legal_boarding_verdict"])

    def test_original_actor_and_input_source_rejections(self):
        site = scene.load_site(self.path)
        sample = self.sample()
        self.assertEqual(scene.controller(scene.measure(site, sample))["brake"], 0)
        sample["driver_observation_event"] = {"source": "camera_visible", "observed": True}
        with self.assertRaisesRegex(ValueError, "original input"):
            scene.measure(site, sample)
        sample["driver_observation_event"]["source"] = "original_driver_input"
        self.assertEqual(scene.controller(scene.measure(site, sample))["brake"], 1)
        sample["stop_actor_id"] = 99
        with self.assertRaisesRegex(ValueError, "transit actors"):
            scene.measure(site, sample)


if __name__ == "__main__":
    unittest.main()
