import json
import hashlib
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from native_motion import capture_speed
from saved_speed import process
from speed_boundary import measure
from delivery_audit import audit_integrity


CASE = "testing__C10301__NRS-484B-600-1e__motor_vehicle_driver__above"


class FakeActor:
    def __init__(self, moving=True):
        self.speed = 0.0
        self.x = 0.0
        self.control = None
        self.moving = moving
        self.commands = []

    def apply_control(self, control):
        self.control = control
        self.commands.append(control)

    def get_velocity(self):
        return SimpleNamespace(x=self.speed, y=0.0, z=0.0)

    def get_transform(self):
        return SimpleNamespace(location=SimpleNamespace(x=self.x, y=0.0, z=0.0))


class FakeWorld:
    def __init__(self, actor, gap_at=None):
        self.actor = actor
        self.frame = 100
        self.elapsed = 0.0
        self.gap_at = gap_at

    def get_settings(self):
        return SimpleNamespace(synchronous_mode=True, fixed_delta_seconds=0.05)

    def tick(self):
        if self.actor.moving:
            control = self.actor.control
            self.actor.speed = max(0.0, self.actor.speed +
                                   0.25 * control.throttle - 0.5 * control.brake)
            self.actor.x += self.actor.speed * 0.05
        self.frame += 2 if self.frame == self.gap_at else 1
        self.elapsed += 0.05
        return self.frame

    def get_snapshot(self):
        return SimpleNamespace(frame=self.frame,
                               timestamp=SimpleNamespace(elapsed_seconds=self.elapsed))


def control(**values):
    return SimpleNamespace(**values)


class NativeMotionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.attempt = Path(self.tmp.name) / "attempt"

    def test_original_tick_capture_and_source_join(self):
        actor = FakeActor()
        receipt = capture_speed(FakeWorld(actor), actor, control, self.attempt,
                                CASE, "native-001", 0.05,
                                diagnostic_fixture=True)
        self.assertEqual(receipt["sample_count"], 900)
        self.assertGreater(receipt["travel_m"], 100)
        self.assertFalse(receipt["physical_acceptance_claimed"])
        self.assertTrue(receipt["diagnostic_fixture"])
        self.assertEqual(actor.commands[-1].brake, 1.0)
        measured = measure(self.attempt, CASE)
        self.assertEqual(measured["source_sha256"], receipt["speed_source_sha256"])
        self.assertTrue(measured["diagnostic_fixture"])
        self.assertEqual(json.loads((self.attempt / "native-motion-receipt.json").read_text()),
                         receipt)
        with self.assertRaisesRegex(ValueError, "diagnostic fixture"):
            process(self.attempt, CASE, Path(self.tmp.name) / "unreviewed.json")
        saved = process(self.attempt, CASE, Path(self.tmp.name) / "diagnostic.json",
                        allow_diagnostic=True)
        self.assertEqual(saved["measurement"]["source_sha256"],
                         receipt["speed_source_sha256"])
        self.assertEqual(saved["legal_judgment"], "unresolved")
        self.assertFalse(saved["physical_acceptance_claimed"])
        receipt_path = self.attempt / "native-motion-receipt.json"
        damaged = json.loads(receipt_path.read_text())
        damaged["speed_source_sha256"] = "0" * 64
        receipt_path.write_text(json.dumps(damaged))
        with self.assertRaisesRegex(ValueError, "source and motion receipt differ"):
            process(self.attempt, CASE, Path(self.tmp.name) / "tampered.json",
                    allow_diagnostic=True)

    def test_frame_gap_and_stalled_motion_rejected_with_brake(self):
        actor = FakeActor()
        with self.assertRaisesRegex(ValueError, "frame identity"):
            capture_speed(FakeWorld(actor, gap_at=150), actor, control,
                          self.attempt, CASE, "native-gap", 0.05,
                          diagnostic_fixture=True)
        self.assertEqual(actor.commands[-1].brake, 1.0)
        self.assertFalse((self.attempt / "original-speed.jsonl").exists())
        stalled = FakeActor(moving=False)
        with self.assertRaisesRegex(ValueError, "did not travel"):
            capture_speed(FakeWorld(stalled), stalled, control,
                          self.attempt, CASE, "native-stalled", 0.05,
                          diagnostic_fixture=True)
        self.assertEqual(stalled.commands[-1].brake, 1.0)

    def test_exact_identity_and_uncertainty_required(self):
        actor = FakeActor()
        world = FakeWorld(actor)
        with self.assertRaisesRegex(ValueError, "unknown exact"):
            capture_speed(world, actor, control, self.attempt, CASE + "-foreign",
                          "native-1", 0.05)
        with self.assertRaisesRegex(ValueError, "unknown exact"):
            capture_speed(world, actor, control, self.attempt,
                          CASE.replace("__above", "__foreign__above"),
                          "native-1", 0.05)
        with self.assertRaisesRegex(ValueError, "uncertainty"):
            capture_speed(world, actor, control, self.attempt, CASE,
                          "native-1", -0.1)
        self.assertEqual(world.frame, 100)

    def test_source_integrity_audit_rejects_missing_and_changed_media(self):
        capture_speed(FakeWorld(FakeActor()), FakeActor(), control, self.attempt,
                      CASE, "native-audit", 0.05, diagnostic_fixture=True)



if __name__ == "__main__":
    unittest.main()
