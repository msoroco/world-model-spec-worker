import importlib.util
import json
from pathlib import Path
import unittest


spec = importlib.util.spec_from_file_location("runner", Path(__file__).resolve().parents[1] / "runner.py")
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


class RunnerPlanTest(unittest.TestCase):
    def setUp(self):
        self.config = json.loads((Path(__file__).resolve().parents[1] / "config.json").read_text())

    def test_exact_plan(self):
        proof = runner.check(self.config)
        self.assertEqual(proof["frame_count"], 600)
        self.assertEqual(len(proof["views"]), 4)
        self.assertFalse(proof["carla_contacted"])

    def test_mode_identity_rejected(self):
        self.config["stop_mode"] = "on_pavement" if self.config["stop_mode"] != "on_pavement" else "off_pavement"
        with self.assertRaisesRegex(ValueError, "case identity changed"):
            runner.check(self.config)

    def test_wrong_cell_rejected(self):
        self.config["cell_id"] = "wrong"
        with self.assertRaisesRegex(ValueError, "assignment identity changed"):
            runner.check(self.config)

    def test_short_capture_rejected(self):
        self.config["frames"] = 599
        with self.assertRaisesRegex(ValueError, "30-second capture required"):
            runner.check(self.config)

    def survey(self):
        return {"source_kind": "original_native_highway_survey",
                "map_name": "reviewed-map", "highway_source_id": "highway-review",
                "district_source_id": "frontage-review", "district": "outside",
                "public_highway_reviewed": True,
                "pavement_edge_source_id": "edge-survey", "offroad_area_source_id": "shoulder-survey",
                "visibility_source_id": "sight-survey",
                "approach_visibility_sources": {
                    "forward": {"source_id": "forward-ray", "path_distance_m": 60.96,
                                "location_xyz_m": [70.96, 2.8, 1.4]},
                    "backward": {"source_id": "backward-ray", "path_distance_m": 60.96,
                                 "location_xyz_m": [-50.96, 2.8, 1.4]}},
                "disabled_failure_source_id": "scenario-failure-trace",
                "spawn_xyz_yaw_deg": [0, 0, 0, 0], "other_spawn_xyz_yaw_deg": [-10, -2, 0, 0],
                "stop_target_xyz_m": [10, 2.8, 0],
                "stop_targets_xyz_m": {"off_pavement": [10, 5.0, 0],
                                       "on_pavement": [10, 2.8, 0],
                                       "disabled_on_pavement": [10, 2.8, 0]},
                "pavement_left_y_m": -3.5, "pavement_right_y_m": 3.5,
                "vehicle_half_width_m": 0.9}

    def test_three_distinct_surveyed_modes(self):
        survey = self.survey()
        self.assertIs(runner.validate_survey(survey), survey)
        survey["stop_targets_xyz_m"]["off_pavement"][1] = 3.0
        with self.assertRaisesRegex(ValueError, "off-pavement stop target overlaps"):
            runner.validate_survey(survey)

    def test_bidirectional_sight_source_required(self):
        survey = self.survey()
        del survey["approach_visibility_sources"]["backward"]
        with self.assertRaisesRegex(ValueError, "both approach visibility sources required"):
            runner.validate_survey(survey)

    def test_nine_rays_per_approach_and_intervening_obstruction(self):
        class Location:
            def __init__(self, x=0, y=0, z=0):
                self.x, self.y, self.z = x, y, z

            def distance(self, other):
                return ((self.x - other.x)**2 + (self.y - other.y)**2 +
                        (self.z - other.z)**2)**0.5

        Carla = type("Carla", (), {"Location": Location})

        class Box:
            def get_world_vertices(self, transform):
                return [Location(x=10, y=2.8, z=1.0) for _ in range(8)]

        class Ego:
            bounding_box = Box()

            def get_transform(self):
                return type("Transform", (), {"location": Location(x=10, y=2.8, z=1.0)})()

        class World:
            def cast_ray(self, origin, target):
                if origin.x < 0:
                    return [type("Hit", (), {"location": Location(x=0, y=2.8, z=1.0)})()]
                return []

        rays = runner.approach_rays(World(), Ego(), self.survey(), Carla)
        self.assertEqual(len(rays["forward"]["ray_clear"]), 9)
        self.assertTrue(all(rays["forward"]["ray_clear"]))
        self.assertFalse(any(rays["backward"]["ray_clear"]))


if __name__ == "__main__":
    unittest.main()
