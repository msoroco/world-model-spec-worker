import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace as Box
import unittest

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
from native_capture import VIEWS, capture
from native_count_capture import CountCapture
from prove_native_count_capture import prove as prove_count
from saved_conditions import measure
from test_native_conditions import Actor, World


class ControlledActor(Actor):
    def __init__(self, actor_id, x):
        super().__init__(actor_id, x)
        self.location.z = 0.0
        self.controls = []

    def apply_control(self, control):
        self.controls.append(control)


class TickWorld(World):
    def __init__(self):
        self.frame = 399

    def get_settings(self):
        return Box(synchronous_mode=True, no_rendering_mode=False,
                   fixed_delta_seconds=.05)

    def tick(self):
        self.frame += 1
        return self.frame

    def get_snapshot(self):
        return Box(frame=self.frame,
                   timestamp=Box(elapsed_seconds=20 + (self.frame - 400) * .05))


class Rig:
    def __init__(self, omit_frame=None):
        self.omit_frame = omit_frame

    def await_frame(self, frame, time_s):
        names = VIEWS if frame != self.omit_frame else VIEWS[:-1]
        return {name: {"frame": frame, "time_s": time_s,
                       "sha256": "a" * 64, "raw_bgra": f"raw/{name}/{frame}.bgra"}
                for name in names}


class FrameMap:
    def __init__(self, path):
        self.stream = Path(path).open("x")
        self.index = 0

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.stream.close()

    def append(self, frame, time_s, **extra):
        self.stream.write(json.dumps({"video_frame": self.index,
                                      "carla_frame": frame, "time_s": time_s, **extra}) + "\n")
        self.index += 1


class NativeCaptureTests(unittest.TestCase):
    def setUp(self):
        self.root = HERE.parents[1] / ".runtime-work"
        self.root.mkdir(exist_ok=True)
        self.world = TickWorld()
        self.ego = ControlledActor(1, 0)
        self.leader = ControlledActor(2, 30)
        self.scene = Box(ego=self.ego, leader=self.leader,
                         targets={"ego_speed_mps": 8.0, "leader_speed_mps": 8.0},
                         source={"packet_sha256": "b" * 64})

    def test_full_900_tick_original_join_and_seal(self):
        with tempfile.TemporaryDirectory(dir=self.root) as directory:
            attempt = Path(directory) / "attempt"
            result = capture(self.world, self.scene, Rig(), attempt, "exact-case",
                             lambda **kw: kw, frame_map_factory=FrameMap)
            self.assertEqual(result["frames"], 900)
            self.assertEqual(len(self.ego.controls), 900)
            measured = measure(attempt, "exact-case")
            self.assertEqual(measured["sample_count"], 900)
            self.assertEqual(measured["provenance_kind"], "native_api_capture")
            self.assertEqual(len((attempt / "trace.jsonl").read_text().splitlines()), 900)
            with self.assertRaisesRegex(ValueError, "retain previous original"):
                capture(self.world, self.scene, Rig(), attempt, "exact-case",
                        lambda **kw: kw, frame_map_factory=FrameMap)

    def test_count_probe_joins_each_original_tick_and_seals_source(self):
        with tempfile.TemporaryDirectory(dir=self.root) as directory:
            attempt = Path(directory) / "attempt"
            actor = object()
            source = CountCapture({
                "case_id": "exact-case", "kind": "additional_pedestrian_count",
                "expected_count": 1, "actors": [actor],
                "declared_blueprint_ids": ["walker.reviewed"],
                "packet_sha256": "c" * 64, "opendrive_sha256": "d" * 64,
            })
            result = capture(
                self.world, self.scene, Rig(), attempt, "exact-case",
                lambda **kw: kw, frame_map_factory=FrameMap,
                count_capture=source,
                count_reader=lambda _: {"actor_id": 9, "type_id": "walker.reviewed",
                                        "alive": True})
            self.assertEqual(result["count_source_sha256"],
                             prove_count(attempt / "original-counts.jsonl",
                                         case_id="exact-case",
                                         kind="additional_pedestrian_count",
                                         packet_sha256="c" * 64,
                                         opendrive_sha256="d" * 64,
                                         declared_blueprint_ids=["walker.reviewed"])["source_sha256"])
            trace = [json.loads(line) for line in (attempt / "trace.jsonl").read_text().splitlines()]
            self.assertEqual([row["count_source_index"] for row in trace], list(range(900)))
            self.assertEqual({row["observed_additional_count"] for row in trace}, {1})

    def test_missing_camera_frame_rejected_without_seal(self):
        with tempfile.TemporaryDirectory(dir=self.root) as directory:
            attempt = Path(directory) / "attempt"
            with self.assertRaisesRegex(ValueError, "four-view frame set incomplete"):
                capture(self.world, self.scene, Rig(omit_frame=401), attempt, "exact-case",
                        lambda **kw: kw, frame_map_factory=FrameMap)
            self.assertFalse((attempt / "original-conditions-seal.json").exists())

    def test_wrong_tick_cadence_and_output_root_rejected(self):
        with tempfile.TemporaryDirectory(dir=self.root) as directory:
            self.world.get_settings = lambda: Box(synchronous_mode=True,
                no_rendering_mode=False, fixed_delta_seconds=.1)
            with self.assertRaisesRegex(ValueError, "20 Hz Native world"):
                capture(self.world, self.scene, Rig(), Path(directory) / "attempt",
                        "exact-case", lambda **kw: kw, frame_map_factory=FrameMap)
        with self.assertRaisesRegex(ValueError, "under .runtime-work"):
            capture(TickWorld(), self.scene, Rig(), HERE / "outside-root-attempt",
                    "exact-case", lambda **kw: kw, frame_map_factory=FrameMap)


if __name__ == "__main__":
    unittest.main()
