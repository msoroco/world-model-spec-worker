"""The Core publisher keeps original walker control and same-frame graph join."""
import io
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pedestrian_core_capture import PedestrianCoreCapture


def vector(x=0, y=0, z=0):
    return types.SimpleNamespace(x=x, y=y, z=z)


class Walker:
    id = 41
    bounding_box = types.SimpleNamespace(
        get_world_vertices=lambda transform: [vector(1, 2, 0)] * 8)

    def get_transform(self):
        return types.SimpleNamespace(location=vector(1, 2, 0),
                                     rotation=types.SimpleNamespace(yaw=12))

    def get_velocity(self):
        return vector(1, 0, 0)

    def get_control(self):
        return types.SimpleNamespace(direction=vector(1, 0, 0), speed=1.4)


class CoreCaptureTests(unittest.TestCase):
    def test_original_walker_control_and_graph_frame(self):
        walker = Walker()
        cap = types.SimpleNamespace(
            closed=False,
            world=types.SimpleNamespace(
                get_snapshot=lambda: types.SimpleNamespace(frame=17),
                get_weather=lambda: types.SimpleNamespace(**{k: 0 for k in
                    ("cloudiness", "precipitation", "precipitation_deposits",
                     "fog_density", "fog_distance", "sun_altitude_angle", "wetness")})),
            map=types.SimpleNamespace(get_waypoint=lambda location: None),
            collector=types.SimpleNamespace(capture=lambda frame, control, observed_evidence:
                {"simulation_time": .85} if frame == 17 and control is None else None),
            user_visibility=False, physical_registry=None,
            map_context={}, trace=io.StringIO(), evidence=io.StringIO(),
            meta={"frames": 0})
        publisher = PedestrianCoreCapture.__new__(PedestrianCoreCapture)
        publisher._capture, publisher.walker = cap, walker
        observation = {"participants": [{"actor_id": walker.id,
                                         "acceleration_method": "original"}]}
        with patch("original_observations.observe", return_value=observation):
            row = publisher.capture(17, .85)
        self.assertEqual(row["walker_control"]["requested_speed_mps"], 1.4)
        self.assertNotIn("control", row)
        self.assertEqual(cap.meta["frames"], 1)
        with self.assertRaisesRegex(ValueError, "current original frame"):
            publisher.capture(18, .9)


if __name__ == "__main__":
    unittest.main()
