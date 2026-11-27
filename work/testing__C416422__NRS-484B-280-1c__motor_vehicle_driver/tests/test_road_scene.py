import hashlib
import importlib.util
import json
import os
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("road_scene", ROOT / "road_scene.py")
scene = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(scene)


def body(x, y):
    return [[x, y, 0], [x + 1, y, 0], [x + 1, y + 1, 0], [x, y + 1, 0]]


class RoadSceneTests(unittest.TestCase):
    def setUp(self):
        # All scratch stays outside the checkpointed work tree.
        scratch = Path(os.environ["SCENARIO_PIPELINE_OUTPUT_ROOT"])
        scratch.mkdir(parents=True, exist_ok=True)
        self.tmp = tempfile.TemporaryDirectory(dir=scratch)
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / "map.xodr").write_text("<OpenDRIVE/>")
        self.site = {"format": "worker-near-road-site", "cell_id": "C416422",
                     "layout": "single_lane_per_direction", "sidewalk_present": True,
                     "map_source": {"path": "map.xodr", "sha256": hashlib.sha256(b"<OpenDRIVE/>").hexdigest()},
                     "road": {"lateral_bounds_m": [-2, 2],
                              "classification_source": "reviewed-map-road",
                              "edge_review_source": "reviewed-map-edges"},
                     "sidewalk": {"lateral_bounds_m": [2.5, 4.5],
                                  "lane_source": "reviewed Sidewalk lane",
                                  "adjacency_source": "reviewed adjacent waypoint"},
                     "ego_start_xy_m": [-30, 0], "ego_end_xy_m": [20, 0],
                     "pedestrian_start_xy_m": [0, 3], "pedestrian_end_xy_m": [1, 3]}
        self.site_path = self.root / "site.json"
        self.save()

    def save(self):
        self.site_path.write_text(json.dumps(self.site))

    def test_site_requires_original_map_and_sidewalk(self):
        self.assertEqual(scene.load_site(self.site_path)["layout"], "single_lane_per_direction")
        self.site["sidewalk_present"] = False
        self.save()
        with self.assertRaisesRegex(ValueError, "sidewalk"):
            scene.load_site(self.site_path)
        self.site["sidewalk_present"] = True
        self.save()
        (self.root / "map.xodr").write_text("changed")
        with self.assertRaisesRegex(ValueError, "stale"):
            scene.load_site(self.site_path)

    def test_pedestrian_route_must_be_on_adjacent_sidewalk(self):
        self.site["pedestrian_end_xy_m"] = [0, 5]
        self.save()
        with self.assertRaisesRegex(ValueError, "not on reviewed sidewalk"):
            scene.load_site(self.site_path)

    def test_original_observation_is_separate_from_visibility(self):
        sample = {"pedestrian_class_source": "actor-blueprint", "driver_control_source": "driver-input-log",
                  "pedestrian_class": "pedestrian", "ego_class": "motor_vehicle",
                  "ego_body_vertices_m": body(-6, 0), "pedestrian_body_vertices_m": body(0, 3),
                  "ego_speed_mps": 4, "ego_brake": 0}
        measured = scene.observed_encounter(scene.load_site(self.site_path), sample)
        self.assertIsNone(measured["driver_observation_event"])
        self.assertEqual(scene.controller(measured, "prompt_brake")["brake"], 0)
        sample["driver_observation_event"] = {"source": "camera_visible", "observed": True}
        with self.assertRaisesRegex(ValueError, "original input"):
            scene.observed_encounter(scene.load_site(self.site_path), sample)
        sample["driver_observation_event"]["source"] = "original_driver_input"
        measured = scene.observed_encounter(scene.load_site(self.site_path), sample)
        self.assertEqual(scene.controller(measured, "prompt_brake")["brake"], 1)
        self.assertEqual(scene.controller(measured, "deferred_brake")["brake"], 0)
        self.assertIsNone(measured["legal_proper_caution_verdict"])
        self.assertIsNone(measured["legal_near_road_verdict"])
        self.assertTrue(measured["pedestrian_bodily_off_road"])

    def test_body_on_road_or_outside_sidewalk_rejected(self):
        sample = {"pedestrian_class_source": "actor-blueprint", "driver_control_source": "driver-input-log",
                  "pedestrian_class": "pedestrian", "ego_class": "motor_vehicle",
                  "ego_body_vertices_m": body(-6, 0), "pedestrian_body_vertices_m": body(0, 1),
                  "ego_speed_mps": 4, "ego_brake": 0}
        with self.assertRaisesRegex(ValueError, "outside reviewed off-road sidewalk"):
            scene.observed_encounter(scene.load_site(self.site_path), sample)
        sample["pedestrian_body_vertices_m"] = body(0, 5)
        with self.assertRaisesRegex(ValueError, "outside reviewed off-road sidewalk"):
            scene.observed_encounter(scene.load_site(self.site_path), sample)


if __name__ == "__main__":
    unittest.main()
