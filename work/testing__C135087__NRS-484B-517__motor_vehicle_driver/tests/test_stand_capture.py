import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


PACKAGE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE))
from stand import SourceError, audit_saved_attempt
from stand_capture import capture
from stand_media_audit import audit as audit_media
from stand_delivery import audit as audit_delivery


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
        scratch = PACKAGE.parents[1] / '.runtime-work' / 'c135087-media-tests'
        scratch.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=scratch)
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

    def test_four_original_video_decodes_and_hash_tamper(self):
        cameras = {}
        for name in ('front', 'rear', 'left', 'right'):
            path = self.root / (name + '.mkv')
            result = subprocess.run([
                'ffmpeg', '-v', 'error', '-f', 'lavfi', '-i',
                'color=c=black:s=16x16:r=20:d=0.2', '-frames:v', '4',
                '-c:v', 'ffv1', '-y', str(path)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            cameras[name] = {'path': path.name, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                             'frame_count': 4, 'fps': 20}
        attempt = {'case_id': 'diagnostic-stand', 'frame_count': 4, 'fps': 20,
                   'cameras': cameras}
        report = audit_media(attempt, self.root, expected_frames=4,
                             dimensions={name: (16, 16) for name in cameras})
        self.assertEqual(report['decoded_view_frames'], 16)
        self.assertTrue(report['diagnostic_fixture'])
        self.assertFalse(report['physical_acceptance'])
        with (self.root / 'front.mkv').open('ab') as stream:
            stream.write(b'changed')
        with self.assertRaisesRegex(SourceError, 'hash mismatch'):
            audit_media(attempt, self.root, expected_frames=4)

    def test_sealed_full_capture_and_video_delivery_join(self):
        for name in ('front', 'rear', 'left', 'right'):
            path = self.root / (name + '.mkv')
            result = subprocess.run([
                'ffmpeg', '-v', 'error', '-f', 'lavfi', '-i',
                'color=c=black:s=16x16:r=20:d=45', '-frames:v', '900',
                '-c:v', 'ffv1', '-y', str(path)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
        capture(self.world, self.actors, observe, 'case-a', 'Town', self.root)
        report = audit_delivery(self.root,
                                dimensions={name: (16, 16) for name in
                                            ('front', 'rear', 'left', 'right')})
        self.assertEqual(report['original_frame_count'], 900)
        self.assertEqual(report['decoded_camera_frames'], 3600)
        self.assertFalse(report['physical_completion'])
        with (self.root / 'front.mkv').open('ab') as stream:
            stream.write(b'changed')
        with self.assertRaisesRegex(SourceError, 'hash mismatch'):
            audit_delivery(self.root)


if __name__ == "__main__":
    unittest.main()
