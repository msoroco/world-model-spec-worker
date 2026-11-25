import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from native_sight_capture import CaptureError, capture
from test_sight import SHA, site


class World:
    def __init__(self, skip=False):
        self.frame = 0
        self.skip = skip
    def tick(self):
        self.frame += 2 if self.skip and self.frame == 5 else 1
        return self.frame
    def get_snapshot(self):
        return SimpleNamespace(frame=self.frame,
                               timestamp=SimpleNamespace(elapsed_seconds=self.frame / 20))


class Ego:
    def get_velocity(self):
        return SimpleNamespace(x=15 * .44704, y=0, z=0)


def route(frame, snapshot, ego):
    if frame < 100: return 31.0, False
    if frame <= 140: return 30.48 * (140 - frame) / 40, False
    if frame <= 160: return -1.0, True
    return -2.0, False


def rays(frame, snapshot, ego, arms):
    return {arm: {"observer_convention": "lane_waypoint_1.4m_bbox_9",
                  "sampled_extent_m": 31.0,
                  "intersection_view": "clear",
                  "traffic_view": "blocked" if arm == "west" else "clear",
                  "ray_frame_source_sha256": SHA} for arm in arms}


class NativeSightCaptureTests(unittest.TestCase):
    def test_original_capture_seals_900_frames_and_measured_rays(self):
        with tempfile.TemporaryDirectory() as temp:
            brakes = []
            output = Path(temp) / "attempt"
            receipt = capture("blocked_at", site(), World(), Ego(), route, rays,
                              lambda ego: brakes.append(ego), output)
            self.assertEqual(len(brakes), 1)
            self.assertEqual(receipt["frame_count"], 900)
            self.assertFalse(receipt["measurement"]["all_views_clear"])
            self.assertIsNone(receipt["legal_conclusion"])
            packet = json.loads((output / "native-sight.json").read_text())
            self.assertEqual([f["frame"] for f in packet["frames"]], list(range(1, 901)))
            self.assertAlmostEqual(receipt["measurement"]["traversal_speed_max_mps"], 15 * .44704)

    def test_frame_gap_rejected_and_brake_applied(self):
        with tempfile.TemporaryDirectory() as temp:
            brakes = []
            with self.assertRaises(CaptureError):
                capture("blocked_at", site(), World(skip=True), Ego(), route, rays,
                        lambda ego: brakes.append(ego), Path(temp) / "attempt")
            self.assertEqual(len(brakes), 1)

    def test_missing_arm_and_missing_authority_source_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            brakes = []
            with self.assertRaises(CaptureError):
                capture("blocked_at", site(), World(), Ego(), route,
                        lambda frame, snap, ego, arms: {"west": rays(frame, snap, ego, arms)["west"]},
                        lambda ego: brakes.append(ego), Path(temp) / "attempt")
            self.assertEqual(len(brakes), 1)
            packet = site(); packet["traffic_controlled_intersection_source_sha256"] = ""
            with self.assertRaises(ValueError):
                capture("blocked_at", packet, World(), Ego(), route, rays,
                        lambda ego: None, Path(temp) / "attempt2")

    def test_output_is_once_only(self):
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "attempt"
            output.mkdir()
            with self.assertRaises(CaptureError):
                capture("blocked_at", site(), World(), Ego(), route, rays,
                        lambda ego: None, output)

    def test_engineering_control_runs_before_each_tick_and_brakes_on_failure(self):
        with tempfile.TemporaryDirectory() as temp:
            world = World()
            controls = []
            brakes = []
            receipt = capture("blocked_at", site(), world, Ego(), route, rays,
                              lambda ego: brakes.append(ego), Path(temp) / "attempt",
                              before_tick=lambda ego: controls.append(world.frame))
            self.assertEqual(len(controls), 900)
            self.assertEqual(controls[:3], [0, 1, 2])
            self.assertEqual(receipt["frame_count"], 900)
            self.assertEqual(len(brakes), 1)
            with self.assertRaisesRegex(RuntimeError, "control failed"):
                capture("blocked_at", site(), World(), Ego(), route, rays,
                        lambda ego: brakes.append(ego), Path(temp) / "failed",
                        before_tick=lambda ego: (_ for _ in ()).throw(RuntimeError("control failed")))
            self.assertEqual(len(brakes), 2)


if __name__ == "__main__": unittest.main()
