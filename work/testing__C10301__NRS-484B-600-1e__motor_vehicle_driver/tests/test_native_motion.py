import json
import hashlib
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from native_motion import capture_speed
from saved_speed import process, process_delivery
from speed_boundary import measure
from delivery_audit import audit_integrity, audit_decoded_media
from capture_finalizer import finalize_capture


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
        return SimpleNamespace(synchronous_mode=True, fixed_delta_seconds=0.05,
                               no_rendering_mode=False)

    def get_actors(self):
        return [self.actor]

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

    def test_existing_original_artifact_rejected_before_native_motion(self):
        for name in ("original-speed.jsonl", "speed-source.json",
                     "native-motion-receipt.json", "camera-frame-readback.json"):
            with self.subTest(name=name):
                with tempfile.TemporaryDirectory() as directory:
                    attempt = Path(directory)
                    (attempt / name).write_text("existing original evidence")
                    actor = FakeActor()
                    world = FakeWorld(actor)
                    with self.assertRaisesRegex(ValueError, "already exists"):
                        capture_speed(world, actor, control, attempt, CASE,
                                      "native-repeat", 0.05,
                                      diagnostic_fixture=True,
                                      camera_frame_reader=lambda frame: {})
                    self.assertEqual(world.frame, 100)
                    self.assertEqual((attempt / name).read_text(),
                                     "existing original evidence")

    def test_source_integrity_audit_rejects_missing_and_changed_media(self):
        actor = FakeActor()
        capture_speed(FakeWorld(actor), actor, control, self.attempt, CASE,
                      "native-audit", 0.05, diagnostic_fixture=True)

        def seal(name, value):
            path = self.attempt / name
            path.write_bytes(value)
            return {"path": name, "sha256": hashlib.sha256(value).hexdigest()}

        frames = [{"frame": 101 + i,
                   "camera_frames": {camera: 101 + i for camera in
                                     ("front", "front_left", "front_right", "rear")}}
                  for i in range(900)]
        frame_map = json.dumps({"case_id": CASE, "native_run_id": "native-audit",
                                "frames": frames}).encode()
        index = {"format": "c10301-capture-index-v1", "case_id": CASE,
                 "frame_count": 900, "diagnostic_fixture": True,
                 "native_motion": seal("native-motion-receipt.json",
                                       (self.attempt / "native-motion-receipt.json").read_bytes()),
                 "frame_map": seal("frame-map.json", frame_map),
                 "cameras": {camera: seal(camera + ".mp4", camera.encode())
                             for camera in ("front", "front_left", "front_right", "rear")}}
        (self.attempt / "capture-index.json").write_text(json.dumps(index))
        with self.assertRaisesRegex(ValueError, "diagnostic fixture"):
            audit_integrity(self.attempt, CASE)
        result = audit_integrity(self.attempt, CASE, allow_diagnostic=True)
        self.assertTrue(result["source_integrity_passed"])
        self.assertFalse(result["full_video_decode"])
        motion_path = self.attempt / "native-motion-receipt.json"
        original_motion = motion_path.read_bytes()
        for field, bad_value in (("travel_m", 2.0), ("format", "wrong-format"),
                                 ("physical_acceptance_claimed", True)):
            damaged = json.loads(original_motion)
            damaged[field] = bad_value
            index["native_motion"] = seal("native-motion-receipt.json",
                                          json.dumps(damaged).encode())
            (self.attempt / "capture-index.json").write_text(json.dumps(index))
            with self.assertRaisesRegex(ValueError, "Native motion and capture index differ"):
                audit_integrity(self.attempt, CASE, allow_diagnostic=True)
        index["native_motion"] = seal("native-motion-receipt.json", original_motion)
        (self.attempt / "capture-index.json").write_text(json.dumps(index))
        (self.attempt / "rear.mp4").write_bytes(b"changed")
        with self.assertRaisesRegex(ValueError, "rear source hash differs"):
            audit_integrity(self.attempt, CASE, allow_diagnostic=True)
        (self.attempt / "rear.mp4").unlink()
        with self.assertRaisesRegex(ValueError, "rear source missing"):
            audit_integrity(self.attempt, CASE, allow_diagnostic=True)
        index["cameras"]["rear"] = {"path": "../foreign.mp4", "sha256": "0" * 64}
        (self.attempt / "capture-index.json").write_text(json.dumps(index))
        with self.assertRaisesRegex(ValueError, "rear binding invalid"):
            audit_integrity(self.attempt, CASE, allow_diagnostic=True)

    def test_finalizer_requires_original_camera_joins_and_seals_once(self):
        actor = FakeActor()
        capture_speed(FakeWorld(actor), actor, control, self.attempt, CASE,
                      "native-finalize", 0.05, diagnostic_fixture=True)
        cameras = ("front", "front_left", "front_right", "rear")
        media = {}
        for camera in cameras:
            path = self.attempt / (camera + ".mp4")
            path.write_bytes(camera.encode())
            media[camera] = path
        frames = [{"frame": 101 + i,
                   "camera_frames": {camera: 101 + i for camera in cameras}}
                  for i in range(900)]
        altered = json.loads(json.dumps(frames))
        altered[10]["camera_frames"]["rear"] += 1
        with self.assertRaisesRegex(ValueError, "camera frame join"):
            finalize_capture(self.attempt, CASE, altered, media)
        self.assertFalse((self.attempt / "capture-index.json").exists())
        index = finalize_capture(self.attempt, CASE, frames, media)
        self.assertEqual(index["frame_count"], 900)
        self.assertTrue(audit_integrity(self.attempt, CASE, allow_diagnostic=True)
                        ["source_integrity_passed"])
        with self.assertRaisesRegex(ValueError, "already exists"):
            finalize_capture(self.attempt, CASE, frames, media)
        descriptor_path = self.attempt / "speed-source.json"
        descriptor = json.loads(descriptor_path.read_text())
        descriptor["diagnostic_fixture"] = False
        descriptor_path.write_text(json.dumps(descriptor))
        motion_path = self.attempt / "native-motion-receipt.json"
        motion = json.loads(motion_path.read_text())
        motion["diagnostic_fixture"] = False
        motion_path.write_text(json.dumps(motion))
        index_path = self.attempt / "capture-index.json"
        index = json.loads(index_path.read_text())
        index["diagnostic_fixture"] = False
        index["native_motion"]["sha256"] = hashlib.sha256(
            motion_path.read_bytes()).hexdigest()
        index_path.write_text(json.dumps(index))
        with self.assertRaisesRegex(ValueError, "camera readback required"):
            audit_integrity(self.attempt, CASE)

    def test_native_camera_readback_seals_and_audit_reopens(self):
        actor = FakeActor()
        cameras = ("front", "front_left", "front_right", "rear")
        receipt = capture_speed(FakeWorld(actor), actor, control, self.attempt,
                                CASE, "native-cameras", 0.05,
                                diagnostic_fixture=True,
                                camera_frame_reader=lambda frame:
                                {camera: frame for camera in cameras})
        self.assertEqual(len(receipt["camera_frame_readback_sha256"]), 64)
        readback_path = self.attempt / "camera-frame-readback.json"
        frames = json.loads(readback_path.read_text())["frames"]
        media = {}
        for camera in cameras:
            path = self.attempt / (camera + ".mp4")
            path.write_bytes(camera.encode())
            media[camera] = path
        finalize_capture(self.attempt, CASE, frames, media)
        self.assertTrue(audit_integrity(self.attempt, CASE, allow_diagnostic=True)
                        ["source_integrity_passed"])
        readback_path.write_text("{}")
        with self.assertRaisesRegex(ValueError, "camera readback hash differs"):
            audit_integrity(self.attempt, CASE, allow_diagnostic=True)

    def test_media_audit_decodes_all_original_frames_and_rejects_truncation(self):
        actor = FakeActor()
        cameras = ("front", "front_left", "front_right", "rear")
        capture_speed(FakeWorld(actor), actor, control, self.attempt,
                      CASE, "native-video", 0.05, diagnostic_fixture=True,
                      camera_frame_reader=lambda frame:
                      {camera: frame for camera in cameras})
        frames = json.loads((self.attempt / "camera-frame-readback.json")
                            .read_text())["frames"]
        video = self.attempt / "front.mkv"
        subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i",
                        "color=c=blue:s=16x16:r=20", "-frames:v", "900",
                        "-c:v", "ffv1", str(video)], check=True,
                       capture_output=True, timeout=120)
        media = {"front": video}
        for camera in cameras[1:]:
            path = self.attempt / (camera + ".mkv")
            path.write_bytes(video.read_bytes())
            media[camera] = path
        finalize_capture(self.attempt, CASE, frames, media)
        result = audit_decoded_media(self.attempt, CASE,
                                     allow_diagnostic=True)
        self.assertTrue(result["full_video_decode"])
        self.assertFalse(result["actual_pixels"])
        self.assertEqual(set(result["decoded_cameras"]), set(cameras))
        delivery_path = Path(self.tmp.name) / "saved-delivery.json"
        delivery = process_delivery(self.attempt, CASE, delivery_path,
                                    allow_diagnostic=True)
        self.assertTrue(delivery["media_audit"]["full_video_decode"])
        self.assertFalse(delivery["physical_acceptance_claimed"])
        cli = Path(__file__).resolve().parents[1] / "saved_speed.py"
        rejected_cli_path = Path(self.tmp.name) / "cli-default.json"
        rejected_cli = subprocess.run(
            [sys.executable, str(cli), "--attempt", str(self.attempt),
             "--case-id", CASE, "--output", str(rejected_cli_path)],
            capture_output=True, text=True, timeout=120)
        self.assertNotEqual(rejected_cli.returncode, 0)
        self.assertIn("diagnostic fixture", rejected_cli.stderr)
        self.assertFalse(rejected_cli_path.exists())
        cli_path = Path(self.tmp.name) / "cli-diagnostic.json"
        accepted_cli = subprocess.run(
            [sys.executable, str(cli), "--attempt", str(self.attempt),
             "--case-id", CASE, "--output", str(cli_path),
             "--allow-diagnostic"], capture_output=True, text=True,
            timeout=120)
        self.assertEqual(accepted_cli.returncode, 0, accepted_cli.stderr)
        self.assertTrue(json.loads(cli_path.read_text())["media_audit"]
                        ["full_video_decode"])
        with self.assertRaisesRegex(ValueError, "already exists"):
            process_delivery(self.attempt, CASE, delivery_path,
                             allow_diagnostic=True)
        short_video = self.attempt / "short.mkv"
        subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i",
                        "color=c=red:s=16x16:r=20", "-frames:v", "899",
                        "-c:v", "ffv1", str(short_video)], check=True,
                       capture_output=True, timeout=120)
        media["rear"].write_bytes(short_video.read_bytes())
        index_path = self.attempt / "capture-index.json"
        index = json.loads(index_path.read_text())
        index["cameras"]["rear"]["sha256"] = hashlib.sha256(
            media["rear"].read_bytes()).hexdigest()
        index_path.write_text(json.dumps(index))
        with self.assertRaisesRegex(ValueError, "frames differ"):
            audit_decoded_media(self.attempt, CASE,
                                allow_diagnostic=True)
        rejected_output = Path(self.tmp.name) / "rejected-delivery.json"
        with self.assertRaisesRegex(ValueError, "frames differ"):
            process_delivery(self.attempt, CASE, rejected_output,
                             allow_diagnostic=True)
        self.assertFalse(rejected_output.exists())
        media["rear"].write_bytes(video.read_bytes()[:500])
        with self.assertRaisesRegex(ValueError, "source hash differs"):
            audit_decoded_media(self.attempt, CASE,
                                allow_diagnostic=True)



if __name__ == "__main__":
    unittest.main()
