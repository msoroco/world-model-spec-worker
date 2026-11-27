"""Construction probes for reviewed flagman and signal actors."""
import hashlib
import json
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parents[1]
REPO = HERE.parents[1]
sys.path.insert(0, str(HERE))
from rail_exception_construction import spawn_exception_actor
from rail_native_runner import run_case


class ExceptionActorTests(unittest.TestCase):
    def setUp(self):
        scratch = REPO / ".runtime-work/rail-exception-construction-tests"
        scratch.mkdir(parents=True, exist_ok=True)
        temp = tempfile.TemporaryDirectory(dir=scratch)
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.road = "a" * 64

    def source(self, setup):
        review = {
            "source_kind": "railway_exception_actor_site",
            "reviewer": "test reviewer", "source_citation": "synthetic CPU fixture",
            "road_sha256": self.road, "exception_setup": setup,
            "blueprint_id": "walker.pedestrian.0001" if setup == "flagman_on_duty"
            else "static.prop.crossing_signal",
            "transform": {"x": 12, "y": 3, "z": 0, "yaw": 90}}
        path = self.root / "actor-review.json"
        path.write_text(json.dumps(review) + "\n")
        return {"reviewed_exception_actor_source": {
            "path": path.name,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}}

    def test_exception_actor_creation_and_lifecycle(self):
        for case_key, setup in (
                ("flagman_16mph", "flagman_on_duty"),
                ("signal_nonwarning_16mph", "visible_nonwarning_signal"),
                ("signal_warning_16mph", "visible_warning_signal")):
            with self.subTest(case_key=case_key):
                packet = self.source(setup)
                actors = []
                class Actor:
                    is_alive = True

                    def get_transform(self):
                        return SimpleNamespace(location=SimpleNamespace(x=12, y=3, z=0))

                    def destroy(self):
                        self.destroyed = True
                class World:
                    def get_blueprint_library(self):
                        return SimpleNamespace(find=lambda name: name)

                    def try_spawn_actor(self, blueprint, transform):
                        self.last_blueprint = blueprint
                        self.last_transform = transform
                        actor = Actor()
                        actors.append(actor)
                        return actor
                world = World()
                actor = spawn_exception_actor(
                    world, lambda **kwargs: kwargs, self.root, packet,
                    self.road, case_key)
                self.assertIs(actor, actors[0])
                self.assertEqual(world.last_transform["yaw"], 90)
                actor.destroy()
                self.assertTrue(actor.destroyed)

    def test_changed_review_and_wrong_case_reject_before_spawn(self):
        packet = self.source("flagman_on_duty")
        world = SimpleNamespace()
        with self.assertRaisesRegex(ValueError, "identity incomplete"):
            spawn_exception_actor(world, lambda **kwargs: kwargs, self.root,
                                  packet, self.road, "signal_warning_16mph")
        (self.root / "actor-review.json").write_text("changed\n")
        with self.assertRaisesRegex(ValueError, "missing or changed"):
            spawn_exception_actor(world, lambda **kwargs: kwargs, self.root,
                                  packet, self.road, "flagman_16mph")

    def test_no_exception_case_does_not_spawn(self):
        self.assertIsNone(spawn_exception_actor(
            SimpleNamespace(), None, self.root, {}, self.road,
            "obscured_16mph"))

    def test_runner_releases_exception_even_if_occluder_destroy_fails(self):
        class Occluder:
            def destroy(self):
                raise RuntimeError("occluder destroy failed")
        class ExceptionActor:
            destroyed = False

            def destroy(self):
                self.destroyed = True
        actor = ExceptionActor()
        camera = SimpleNamespace(start=lambda: None, stop=lambda: None,
                                 read=lambda *args: None)
        world = SimpleNamespace(get_map=lambda: SimpleNamespace(
            to_opendrive=lambda: "reviewed road"))
        packet = {"assignment_id": HERE.name, "road_sha256": "a" * 64,
                  "route_source": {}, "route_source_sha256": "b" * 64,
                  "rail_ray_geometry_source": {},
                  "rail_ray_geometry_source_sha256": "c" * 64,
                  "rail_exception_review_source": {},
                  "rail_exception_review_sha256": "d" * 64}
        with (patch("rail_native_runner.read_reviewed_site"),
              patch("rail_native_runner._reviewed_source", return_value=self.root),
              patch("rail_native_runner.ReviewedRailRouteReader",
                    return_value=SimpleNamespace(points=[(0, 0), (1, 0)])),
              patch("rail_native_runner.ReviewedRailRayReader"),
              patch("rail_native_runner.ReviewedRailExceptionReader"),
              patch("rail_native_runner.spawn_occluder", return_value=Occluder()),
              patch("rail_native_runner.spawn_exception_actor", return_value=actor),
              patch("rail_native_runner.capture", side_effect=ValueError("capture failed"))):
            with self.assertRaisesRegex(RuntimeError, "occluder destroy failed"):
                run_case(case_key="flagman_16mph", packet=packet,
                         attempt_root=self.root, world=world, ego=object(),
                         location_factory=lambda *args: None,
                         transform_factory=lambda **kwargs: None,
                         original_exception_reader=lambda *args: {},
                         camera_adapter=camera,
                         control_factory=lambda **kwargs: None,
                         brake=lambda actor: None)
        self.assertTrue(actor.destroyed)


if __name__ == "__main__":
    unittest.main()
