import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest


PACKAGE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE))
from stand import SourceError, audit_saved_attempt
from stand_capture import capture


class Actor:
    def __init__(self, actor_id, speed=0):
        self.id, self.speed = actor_id, speed

    def get_velocity(self):
        return type("Vector", (), {"x": self.speed, "y": 0, "z": 0})()


class World:
    def __init__(self):
        self.index = -1
        self.settings = type("Settings", (), {"synchronous_mode": True,
                                              "fixed_delta_seconds": .05})()
        self.map = type("Map", (), {"name": "Town"})()

    def get_settings(self):
        return self.settings

    def get_map(self):
        return self.map

    def tick(self):
        self.index += 1
        return 100 + self.index

    def get_snapshot(self):
        return type("Snapshot", (), {"frame": 100 + self.index,
                                      "timestamp": type("Timestamp", (), {
                                          "elapsed_seconds": self.index / 20})()})()


def observe(snapshot, actors):
    return {"passenger_loading_active": snapshot.frame < 550,
            "entrant_waiting": snapshot.frame >= 300,
            "entrant_about_to_enter": snapshot.frame < 300,
            "access_obstructed": snapshot.frame >= 400}


class CaptureTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.world = World()
        self.actors = {"subject": Actor(10), "entrant": Actor(11, 2),
                       "passenger": Actor(12)}
        for name in ("front", "rear", "left", "right"):
            (self.root / (name + ".mkv")).write_bytes((name + " fixture bytes").encode())

    def test_original_rows_and_saved_audit(self):
        attempt = capture(self.world, self.actors, observe, "case-a", "Town", self.root)
        self.assertEqual(attempt["first_frame"], 100)
        self.assertEqual(len(json.loads((self.root / "actor-rows.json").read_text())), 900)
        self.assertEqual(audit_saved_attempt(attempt, self.root)["measurement"]["source_frame_count"], 900)
        self.assertTrue((self.root / "attempt-source.json").is_file())
        self.assertEqual(attempt["actor_rows"]["sha256"],
                         hashlib.sha256((self.root / "actor-rows.json").read_bytes()).hexdigest())

    def test_missing_camera_rejected_before_ticking(self):
        (self.root / "rear.mkv").unlink()
        with self.assertRaisesRegex(SourceError, "camera source"):
            capture(self.world, self.actors, observe, "case-a", "Town", self.root)
        self.assertEqual(self.world.index, -1)

    def test_wrong_clock_or_actor_rejected(self):
        self.world.settings.fixed_delta_seconds = .1
        with self.assertRaisesRegex(SourceError, "20 Hz"):
            capture(self.world, self.actors, observe, "case-a", "Town", self.root)
        self.world.settings.fixed_delta_seconds = .05
        self.actors["passenger"] = self.actors["entrant"]
        with self.assertRaisesRegex(SourceError, "duplicate"):
            capture(self.world, self.actors, observe, "case-a", "Town", self.root)

    def test_missing_live_observation_rejected(self):
        with self.assertRaisesRegex(SourceError, "readback"):
            capture(self.world, self.actors, lambda snapshot, actors: {
                "passenger_loading_active": True}, "case-a", "Town", self.root)
        self.assertFalse((self.root / "actor-rows.json").exists())


if __name__ == "__main__":
    unittest.main()
