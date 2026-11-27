import datetime as dt
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("night_parking_capture", ROOT / "night_parking_capture.py")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class Body:
    def get_world_vertices(self, transform):
        return [SimpleNamespace(x=transform.location.x + dx, y=transform.location.y + dy)
                for dx, dy in ((-1, -1), (1, -1), (1, 1), (-1, 1), (-1, -1), (1, -1), (1, 1), (-1, 1))]


class Actor:
    bounding_box = Body()

    def __init__(self, x):
        self.x = x

    def get_transform(self):
        return SimpleNamespace(location=SimpleNamespace(x=self.x, y=0, z=0), rotation=SimpleNamespace(yaw=0))

    def get_velocity(self):
        return SimpleNamespace(x=0, y=0, z=0)


class World:
    def __init__(self, skip=False):
        self.frame = 99
        self.skip = skip

    def tick(self):
        self.frame += 2 if self.skip and self.frame == 100 else 1
        return self.frame

    def get_snapshot(self):
        return SimpleNamespace(frame=self.frame, timestamp=SimpleNamespace(elapsed_seconds=self.frame / 20))


class Sink:
    def __init__(self):
        self.rows = []

    def append(self, *args):
        self.rows.append(args)

    def capture(self, *args):
        self.rows.append(args)


class CaptureTests(unittest.TestCase):
    def test_original_two_actor_tick_capture_and_gaps(self):
        start = MODULE.utc_start("2026-11-27", "02:00:00")
        self.assertEqual(start, dt.datetime(2026, 11, 27, 10, tzinfo=dt.timezone.utc))
        with tempfile.TemporaryDirectory(dir=Path.cwd() / ".runtime-work") as tmp:
            root = Path(tmp)
            pipeline, cameras, mapping = Sink(), Sink(), Sink()
            receipt = MODULE.capture_ticks(World(), Actor(2), Actor(8), pipeline, cameras, mapping,
                                           root, frame_count=3, civil_start_utc=start,
                                           subject_on_street=lambda actor: True,
                                           subject_parked=lambda index, actor: True, diagnostic=True)
            self.assertEqual(receipt["frames"], 3)
            self.assertEqual(len(pipeline.rows), 3)
            self.assertEqual(len(cameras.rows), 3)
            self.assertEqual(len(mapping.rows), 3)
            details = [json.loads(line) for line in (root / "night-parking-trace.jsonl").read_text().splitlines()]
            self.assertEqual(details[0]["frame"], 100)
            self.assertEqual(details[-1]["frame"], 102)
            self.assertEqual(details[0]["other_vehicle"]["center_xy_m"], [8, 0])
        with tempfile.TemporaryDirectory(dir=Path.cwd() / ".runtime-work") as tmp:
            with self.assertRaisesRegex(ValueError, "identity discontinuity"):
                MODULE.capture_ticks(World(skip=True), Actor(2), Actor(8), Sink(), Sink(), Sink(),
                                     tmp, frame_count=3, civil_start_utc=start,
                                     subject_on_street=lambda actor: True,
                                     subject_parked=lambda index, actor: True, diagnostic=True)
        with tempfile.TemporaryDirectory(dir=Path.cwd() / ".runtime-work") as tmp:
            with self.assertRaisesRegex(ValueError, "full nighttime duration"):
                MODULE.capture_ticks(World(), Actor(2), Actor(8), Sink(), Sink(), Sink(),
                                     tmp, frame_count=3, civil_start_utc=start,
                                     subject_on_street=lambda actor: True,
                                     subject_parked=lambda index, actor: True)


if __name__ == "__main__":
    unittest.main()
