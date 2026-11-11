"""Exercise stopped apparatus runner calls and cleanup without CARLA."""
import json
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch


FOLDER = Path(__file__).resolve().parents[1]
ROOT = FOLDER.parents[1]
sys.path.insert(0, str(FOLDER))
sys.path.insert(1, str(ROOT / "runtime/scenario_pipeline"))

import stopped_runner
from worker_exchange import native_output


class FakeActor:
    def __init__(self):
        self.controls = []
        self.destroyed = False

    def apply_control(self, value):
        self.controls.append(value)

    def get_light_state(self):
        return 1

    def destroy(self):
        self.destroyed = True


class FakeWorld:
    def __init__(self):
        self.synchronous_mode = False
        self.fixed_delta_seconds = None
        self.frame = 100
        self.actors = []
        self.mapping = types.SimpleNamespace(name="fake-crest")

    def get_settings(self):
        return types.SimpleNamespace(synchronous_mode=self.synchronous_mode,
                                     fixed_delta_seconds=self.fixed_delta_seconds)

    def apply_settings(self, setting):
        self.synchronous_mode = setting.synchronous_mode
        self.fixed_delta_seconds = setting.fixed_delta_seconds

    def get_map(self):
        return self.mapping

    def get_blueprint_library(self):
        return types.SimpleNamespace(find=lambda name: name)

    def try_spawn_actor(self, *_):
        actor = FakeActor()
        self.actors.append(actor)
        return actor

    def tick(self):
        self.frame += 1
        return self.frame

    def get_snapshot(self):
        return types.SimpleNamespace(frame=self.frame,
                                     timestamp=types.SimpleNamespace(elapsed_seconds=self.frame / 20))


class FakeCamera:
    instances = []

    def __init__(self, *args):
        self.frames = []
        self.closed = False
        self.__class__.instances.append(self)

    def wait_for_frame(self, frame):
        self.frames.append(frame)

    def verify_frames(self, frames):
        if self.frames != frames:
            raise ValueError("Camera/source frame join differs")

    def close(self):
        self.closed = True


class FakeSession:
    instances = []

    def __init__(self, *args):
        self.frames = []
        self.closed = False
        self.__class__.instances.append(self)

    def capture(self, frame, time_s, **readbacks):
        if not isinstance(readbacks["warning_lamp_readback"], bool):
            raise ValueError("Warning lamp readback missing")
        self.frames.append((frame, time_s))

    def close(self):
        self.closed = True


class FakePipeline:
    instances = []

    def __init__(self, *args, **kwargs):
        self.closed = False
        self.__class__.instances.append(self)

    def close(self, **kwargs):
        self.closed = True


class StoppedRunnerTests(unittest.TestCase):
    def test_both_stopped_branches_create_capture_and_restore(self):
        FakeSession.instances.clear()
        FakePipeline.instances.clear()
        FakeCamera.instances.clear()
        for branch, target, park in (("stopped_drive_to", 450, False),
                                     ("stopped_park", 550, True)):
            with self.subTest(branch=branch), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                config = {
                    "law_id": "NRS-484B-710", "cell_id": "C102304",
                    "actor": "motor_vehicle_driver",
                    "selected_case_id": stopped_runner.ASSIGNMENT + "__" + branch + "_" + str(target) + "ft",
                    "fire_branch": branch, "target_distance_ft": target,
                    "rate_hz": 20, "duration_s": 8, "frames": 160,
                    "required_atoms": [], "case": {"recording_description": {"channels": []}},
                    "fire_context": {"alarm_response_source": "authored dispatch premise",
                                     "apparatus_answered_alarm": True,
                                     "subject_authorized_emergency": False,
                                     "subject_official_business": False},
                }
                (root / "config.json").write_text(json.dumps(config))
                world = FakeWorld()
                controls = []
                route = {"apparatus": types.SimpleNamespace(transform="apparatus"),
                         "ego": types.SimpleNamespace(transform="ego"),
                         "road_id": 7, "lane_id": -1}
                carla = types.SimpleNamespace(
                    Client=lambda *_: types.SimpleNamespace(set_timeout=lambda *_: None,
                                                            get_world=lambda: world),
                    VehicleControl=lambda **kw: types.SimpleNamespace(**kw),
                    VehicleLightState=types.SimpleNamespace(Special1=1, Special2=2))
                with patch.dict(sys.modules, {"carla": carla,
                                              "pipeline_capture": types.SimpleNamespace(PipelineCapture=FakePipeline)}), \
                     patch.object(stopped_runner, "select_crest_route", return_value=route) as route_call, \
                     patch.object(stopped_runner, "control_step", side_effect=lambda *a, **kw: controls.append(kw)), \
                     patch.object(stopped_runner, "FFmpegSourceSink", side_effect=lambda *a: types.SimpleNamespace(close=lambda: None)) as sink, \
                     patch.object(stopped_runner, "FireCameraCapture", side_effect=FakeCamera) as camera, \
                     patch.object(stopped_runner, "FireCaptureSession", side_effect=FakeSession), \
                     patch.object(native_output, "seal_capture") as seal:
                    stopped_runner.run(root, "localhost", 2000)
                self.assertEqual(route_call.call_args.kwargs["target_gap_ft"], target + 100)
                self.assertEqual(sink.call_count, 4)
                self.assertEqual(FakeCamera.instances[-1].frames, list(range(101, 261)))
                self.assertTrue(FakeCamera.instances[-1].closed)
                self.assertEqual(len(controls), 160)
                self.assertTrue(all(row["target_centre_ft"] == target and row["park"] is park
                                    for row in controls))
                self.assertEqual(len(FakeSession.instances[-1].frames), 160)
                self.assertTrue(FakeSession.instances[-1].closed)
                self.assertTrue(FakePipeline.instances[-1].closed)
                self.assertTrue(all(actor.destroyed for actor in world.actors))
                self.assertFalse(world.synchronous_mode)
                self.assertIsNone(world.fixed_delta_seconds)
                self.assertEqual(seal.call_args.kwargs["frames"], 160)
                self.assertTrue((root / "acquisition-provenance.json").is_file())

    def test_wrong_branch_and_missing_alarm_answer_rejected(self):
        config = {"law_id": "NRS-484B-710", "cell_id": "C102304",
                  "actor": "motor_vehicle_driver", "fire_branch": "traveling_follow",
                  "target_distance_ft": 500}
        with self.assertRaisesRegex(ValueError, "branch or numeric"):
            stopped_runner.check_config(config)
        config.update(fire_branch="stopped_drive_to", target_distance_ft=500,
                      selected_case_id=stopped_runner.ASSIGNMENT + "__stopped_drive_to_500ft",
                      rate_hz=20, frames=160, duration_s=8,
                      case={"recording_description": {}},
                      fire_context={"alarm_response_source": "authored dispatch",
                                    "apparatus_answered_alarm": False,
                                    "subject_authorized_emergency": False,
                                    "subject_official_business": False})
        with self.assertRaisesRegex(ValueError, "answer-to-alarm"):
            stopped_runner.check_config(config)


if __name__ == "__main__":
    unittest.main()
