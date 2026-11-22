"""Exercise Native transform, bounding box, velocity and control acquisition."""
from io import StringIO
import json
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from parking_native_capture import append_frame, capture_frame


class Point:
    def __init__(self, x, y, z=0):
        self.x, self.y, self.z = x, y, z


class FakeCarla:
    Location = Point


class Transform:
    def transform(self, point):
        return Point(point.x + 10, point.y + 2, point.z)

    def get_forward_vector(self):
        return Point(1, 0)


class Vehicle:
    bounding_box = type("Box", (), {"location": Point(0, 0),
                                    "extent": Point(2.25, 1, 1)})()

    def get_transform(self):
        return Transform()

    def get_velocity(self):
        return Point(0, 0)

    def get_control(self):
        return type("Control", (), {"throttle": 0, "steer": 0, "brake": 1})()


class NativeCaptureTests(unittest.TestCase):
    def test_original_native_calls_and_jsonl(self):
        record = capture_frame(Vehicle(), 7, .35, FakeCarla)
        self.assertEqual(record["body_vertices_xy_m"],
                         [[7.75, 1], [12.25, 1], [12.25, 3], [7.75, 3]])
        self.assertEqual(record["speed_m_s"], 0)
        stream = StringIO()
        append_frame(stream, record)
        self.assertEqual(json.loads(stream.getvalue()), record)

    def test_invalid_frame_or_native_control_rejected(self):
        with self.assertRaisesRegex(ValueError, "world frame"):
            capture_frame(Vehicle(), -1, 0, FakeCarla)

        class BadVehicle(Vehicle):
            def get_control(self):
                return type("Control", (), {"throttle": 2, "steer": 0, "brake": 0})()

        with self.assertRaisesRegex(ValueError, "control outside"):
            capture_frame(BadVehicle(), 0, 0, FakeCarla)


if __name__ == "__main__":
    unittest.main()
