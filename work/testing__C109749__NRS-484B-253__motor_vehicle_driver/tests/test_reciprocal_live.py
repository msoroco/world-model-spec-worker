import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from reciprocal_live import ReciprocalControls, ReciprocalTickAdapter, make_scene_factory
from carla_live_adapter import WorldLease
from test_carla_scene_factory import API, World, packet, request
from test_native_acquisition import waypoint


class Later:
    id = 303

    def get_control(self):
        return SimpleNamespace(brake=0.8)

    def get_velocity(self):
        return SimpleNamespace(length=lambda: 2.0)


class Base:
    ego = SimpleNamespace(id=101)
    opponent = SimpleNamespace(id=202)
    attestation = {"native_map_sha256": "a" * 64}

    def source_attestation(self):
        return {"native_origin": True}

    def tick(self):
        return 17, .85, {"ego_actor_id": 101, "opponent_actor_id": 202}, {"overview": b"png"}


class ReciprocalLiveTests(unittest.TestCase):
    def test_third_actor_same_tick_original_control(self):
        with patch("reciprocal_live._vertices", return_value=[[0, 0, 0]] * 8), \
             patch("reciprocal_live._heading", return_value=[-1, 0]):
            adapter = ReciprocalTickAdapter(Base(), Later())
            frame, time_s, primary, cameras, later = adapter.tick()
        self.assertEqual((frame, time_s), (17, .85))
        self.assertEqual(later["later_opponent_actor_id"], 303)
        self.assertTrue(later["later_opponent_braking"])
        self.assertEqual(later["later_opponent_driver_control_source"], "original Native get_control")
        self.assertEqual(primary["ego_actor_id"], 101)
        self.assertEqual(cameras["overview"], b"png")

    def test_alias_rejected(self):
        bad = SimpleNamespace(id=202)
        with self.assertRaisesRegex(ValueError, "aliases"):
            ReciprocalTickAdapter(Base(), bad)

    def test_later_wait_control_contrast(self):
        request = {"ego_route": [{"x_m": 0, "y_m": 0}, {"x_m": 10, "y_m": 0}],
                   "initial_opponent_route": [{"x_m": 0, "y_m": 1}, {"x_m": 10, "y_m": 1}],
                   "later_opposing_route": [{"x_m": 10, "y_m": 1}, {"x_m": 0, "y_m": 1}],
                   "controller": {"wait_for_initial_opponent": True,
                                  "wait_for_later_opponent": True, "target_speed_mps": 5}}
        actor = object()
        with patch.object(ReciprocalControls, "_inside", side_effect=[False, False, True]), \
             patch.object(ReciprocalControls, "_drive", return_value=(1, False)) as drive:
            control = ReciprocalControls(object(), request, {"intersection_polygon": []}, actor)
            control(actor, actor)
        self.assertEqual(drive.call_args.args[-1], 0.0)
        request["controller"]["wait_for_later_opponent"] = False
        with patch.object(ReciprocalControls, "_inside", side_effect=[False, False, True]), \
             patch.object(ReciprocalControls, "_drive", return_value=(1, False)) as drive:
            control = ReciprocalControls(object(), request, {"intersection_polygon": []}, actor)
            control(actor, actor)
        self.assertEqual(drive.call_args.args[-1], 5.0)

    def test_reviewed_factory_owns_seven_actors(self):
        world = World()
        p = packet(world)
        req = request(world, reciprocal=True)
        req["later_opposing_route"] = [waypoint(0, 15, None),
                                         waypoint(0, 6, None), waypoint(0, -15, None)]
        with WorldLease(world) as lease:
            scene = make_scene_factory(API)(world=world, request=req, packet=p, lease=lease)
            self.assertEqual(len(lease.owned), 7)
            self.assertEqual(len({scene[name].id for name in ("ego", "opponent", "later")}), 3)
            scene["control_step"](scene["ego"], scene["opponent"])
            self.assertEqual(len(scene["later"].controls), 1)
        self.assertTrue(all(actor.destroyed for actor in world.actors))

    def test_reviewed_map_drift_rejected_before_any_spawn(self):
        world = World()
        p = packet(world)
        p["map_sha256"] = "0" * 64
        req = request(world, reciprocal=True)
        req["later_opposing_route"] = [waypoint(0, 15, None), waypoint(0, -15, None)]
        with WorldLease(world) as lease:
            with self.assertRaisesRegex(ValueError, "OpenDRIVE"):
                make_scene_factory(API)(world=world, request=req, packet=p, lease=lease)
            self.assertEqual(lease.owned, [])


if __name__ == "__main__":
    unittest.main()
