import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from native_adapter import Adapter, VIEWS, corners, station, steering_to
from yield_view import CASES


def reviewed_site():
    return {
        "route_xy": [[-20, 0], [-4, 0], [4, 0]],
        "through_spawn_xy": [0, -20],
        "ego_spawn_pose_xyzyaw": [-20, 0, 0.5, 0],
        "through_spawn_pose_xyzyaw": [0, -20, 0.5, 90],
        "ego_route_xy": [[-20, 0], [-4, 0], [4, 0]],
        "through_route_xy": [[0, -20], [0, -4], [0, 4]],
        "ego_station_origin_xy": [0, 0],
        "through_station_origin_xy": [0, 0],
        "ego_station_axis_xy": [1, 0],
        "through_station_axis_xy": [0, 1],
        "vehicle_blueprints": {"ego": "vehicle.a", "through": "vehicle.b"},
        "camera_poses_xyzyaw": {view: [0, 0, 4, 0] for view in VIEWS},
        "sight_observation": {"source": "original_review"},
        "through_intersection_entry_station_m": -2,
        "through_intersection_exit_station_m": 2,
        "camera_fov_deg": {view: 90 for view in VIEWS},
    }


class AdapterContract(unittest.TestCase):
    def adapter(self):
        adapter = Adapter.__new__(Adapter)
        adapter.site = None
        adapter.case = None
        return adapter

    def test_reviewed_geometry_and_blueprints_required(self):
        site = reviewed_site()
        self.adapter().bind_site(site, CASES[0])
        for name, value in (("camera_poses_xyzyaw", {}),
                            ("vehicle_blueprints", {}),
                            ("ego_station_axis_xy", [2, 0]),
                            ("through_route_xy", None),
                            ("camera_fov_deg", {}),
                            ("through_intersection_exit_station_m", -3)):
            bad = {**site, name: value}
            with self.subTest(name=name), self.assertRaises(ValueError):
                self.adapter().bind_site(bad, CASES[0])

    def test_officer_requires_original_actor(self):
        with self.assertRaisesRegex(ValueError, "officer actor"):
            self.adapter().bind_site(reviewed_site(), CASES[3])

    def test_station_and_body_geometry(self):
        actor = SimpleNamespace(
            bounding_box=SimpleNamespace(extent=SimpleNamespace(x=2, y=1, z=.5),
                                         location=SimpleNamespace(x=0, y=0, z=0)),
            get_transform=lambda: SimpleNamespace(
                location=SimpleNamespace(x=3, y=4, z=0),
                rotation=SimpleNamespace(yaw=0)))
        vertices = corners(actor)
        self.assertEqual(len(vertices), 8)
        self.assertEqual(min(station(v, [0, 0], [1, 0]) for v in vertices), 1)
        self.assertEqual(max(station(v, [0, 0], [1, 0]) for v in vertices), 5)
        self.assertEqual(steering_to(actor.get_transform().location, 0, [4, 4]), 0)

    def test_stop_hold_does_not_fabricate_reference_event(self):
        position = SimpleNamespace(x=-3, y=0, z=0)
        actor = SimpleNamespace(
            bounding_box=SimpleNamespace(extent=SimpleNamespace(x=2, y=1, z=.5),
                                         location=SimpleNamespace(x=0, y=0, z=0)),
            get_transform=lambda: SimpleNamespace(location=position,
                                                  rotation=SimpleNamespace(yaw=0)),
            get_velocity=lambda: SimpleNamespace(x=0, y=0),
            apply_control=lambda control: None)
        adapter = self.adapter()
        adapter.site = {**reviewed_site(), "nearest_view_station_m": 0}
        adapter.actors = {"ego": actor}
        adapter.routes = {"ego": [[-20, 0], [4, 0]]}
        adapter.targets = {"ego": 1}
        adapter.policy = "stop"
        adapter.reference_seen = False
        adapter.reference_hold = 0
        adapter.stop_released = False
        adapter.carla = SimpleNamespace(VehicleControl=lambda **kwargs: kwargs)
        for _ in range(20):
            adapter._drive("ego")
        self.assertTrue(adapter.stop_released)
        self.assertFalse(adapter.reference_seen)

    def test_failed_camera_start_still_restores_world(self):
        events = []
        sensor = SimpleNamespace(stop=lambda: events.append("stop"),
                                 destroy=lambda: events.append("destroy"))
        adapter = self.adapter()
        adapter.sensors = {"overview": sensor}
        adapter.officer = None
        adapter.world = SimpleNamespace(apply_settings=lambda value: events.append(value))
        adapter.restore_settings("original_settings")
        self.assertEqual(events, ["stop", "destroy", "original_settings"])
        self.assertEqual(adapter.sensors, {})

    def test_unreadable_spawn_is_destroyed(self):
        events = []
        actor = SimpleNamespace(id=7, destroy=lambda: events.append("destroy"))
        adapter = self.adapter()
        adapter.world = SimpleNamespace(try_spawn_actor=lambda blueprint, pose: actor,
                                        get_actor=lambda actor_id: None)
        with self.assertRaisesRegex(ValueError, "readback failed"):
            adapter.spawn_checked("blueprint", "pose", "camera")
        self.assertEqual(events, ["destroy"])


if __name__ == "__main__":
    unittest.main()
