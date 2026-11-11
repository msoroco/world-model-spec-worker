import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest


MODULE = Path(__file__).resolve().parents[1] / "alley_source_capture.py"
spec = importlib.util.spec_from_file_location("alley_source_capture", MODULE)
source = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = source
spec.loader.exec_module(source)


class Vertex:
    def __init__(self, x, y, z):
        self.x, self.y, self.z = x, y, z


class Box:
    def __init__(self, cx):
        self.cx = cx

    def get_world_vertices(self, _):
        return [Vertex(self.cx+x, y, z) for z in (0, 2)
                for x, y in ((-.3, -.2), (.3, -.2), (.3, .2), (-.3, .2))]


class Actor:
    def __init__(self, actor_id, x):
        self.id = actor_id
        self.bounding_box = Box(x)

    def get_transform(self):
        class Transform:
            def get_forward_vector(self):
                return Vertex(1, 0, 0)
        return Transform()

    def get_velocity(self):
        return Vertex(5, 0, 0)

    def get_acceleration(self):
        return Vertex(-2, 0, 0)


class SourceCaptureTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.actors = [Actor(1, 0), Actor(2, 2), Actor(3, 3)]

    def test_writes_measured_source_and_rejects_skipped_frame(self):
        with source.AlleySourceRecorder(self.root, *self.actors) as recorder:
            first = recorder.append(10, 0.0)
            self.assertEqual(len(first["pedestrian_corners"]), 4)
            with self.assertRaisesRegex(ValueError, "Missing or unordered"):
                recorder.append(12, .1)
            recorder.append(11, .05)
        rows = [json.loads(line) for line in (self.root / "participant_footprints.jsonl").read_text().splitlines()]
        self.assertEqual([row["frame"] for row in rows], [10, 11])
        motion = [json.loads(line) for line in (self.root / "ego_motion.jsonl").read_text().splitlines()]
        self.assertEqual(motion[0]["velocity_xy"], [5.0, 0.0])

    def test_rejects_duplicate_participant_and_bad_geometry(self):
        with self.assertRaisesRegex(ValueError, "distinct Native IDs"):
            source.AlleySourceRecorder(self.root, self.actors[0], self.actors[0], self.actors[2])
        self.actors[0].bounding_box.get_world_vertices = lambda _: [Vertex(0, 0, 0)]
        with source.AlleySourceRecorder(self.root, *self.actors) as recorder:
            with self.assertRaisesRegex(ValueError, "eight bounding-box"):
                recorder.append(10, 0.0)


if __name__ == "__main__":
    unittest.main()
