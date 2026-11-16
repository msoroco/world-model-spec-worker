import sys
import json
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path
from queue import Queue
from types import SimpleNamespace as NS
from unittest.mock import patch


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from runner import _joined_frame, check_config, capture


def config():
    pose = {"location": {"x": 0, "y": 0, "z": 3},
            "rotation": {"pitch": -10, "yaw": 0, "roll": 0}}
    return {"selected_case_id": "testing__C10301__NRS-484B-600-1e__motor_vehicle_driver__source_verified_below_80",
            "law_id": "NRS-484B-600-1e", "cell_id": "C10301", "actor": "motor_vehicle_driver",
            "duration_s": 30, "fps": 20, "rate_hz": 20, "requested_speed_mph": 79,
            "recording_description": {"channels": []},
            "camera_transforms": {name: pose for name in
                                  ("overview", "approach", "reference_corner", "driver_reference")},
            "corridor_context": {"native_map_id": "TownX", "reviewed_road_id": 4,
                                 "reviewed_lane_id": -1, "minimum_length_m": 500,
                                 "subject_blueprint_id": "vehicle.test",
                                 "route_source": "reviewed Native map",
                                 "alley_source": "authority and map review",
                                 "access_aisle_source": "authority and map review",
                                 "road_authority_source": "authority review"}}


class RunnerTests(unittest.TestCase):
    def test_pure_check_accepts_exact_sources_without_carla(self):
        self.assertEqual(check_config(config())["fps"], 20)

    def test_rejects_missing_camera_and_unsupported_rate(self):
        value = config()
        del value["camera_transforms"]["approach"]
        with self.assertRaisesRegex(ValueError, "four named"):
            check_config(value)
        value = config()
        value["fps"] = 10
        with self.assertRaisesRegex(ValueError, "20 Hz"):
            check_config(value)

    def test_joins_exact_sensor_tick_and_rejects_skipped_tick(self):
        queue = Queue()
        queue.put(NS(frame=100))
        queue.put(NS(frame=101))
        self.assertEqual(_joined_frame(queue, 101).frame, 101)
        queue.put(NS(frame=103))
        with self.assertRaisesRegex(ValueError, "join failed"):
            _joined_frame(queue, 102)

    def test_capture_writes_original_sources_and_seals_after_restore(self):
        sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "runtime/scenario_pipeline"))
        from worker_exchange import world_restore

        class FakeSensor:
            def __init__(self): self.callback = None
            def listen(self, callback): self.callback = callback

        class FakeWorld:
            def __init__(self):
                self.frame = 100
                self.sensors = {name: FakeSensor() for name in config()["camera_transforms"]}
                self.settings = NS(synchronous_mode=False, fixed_delta_seconds=None)
            def get_settings(self): return self.settings
            def apply_settings(self, value): self.settings = value
            def tick(self):
                self.frame += 1
                for sensor in self.sensors.values(): sensor.callback(NS(frame=self.frame, raw_data=b"raw"))
                return self.frame
            def get_snapshot(self):
                return NS(frame=self.frame, timestamp=NS(elapsed_seconds=self.frame * .05))

        class FakeVehicle:
            id = 42
            def get_velocity(self): return NS(x=10, y=0, z=0)
            def get_transform(self):
                return NS(location=NS(x=1, y=0, z=0), rotation=NS(yaw=0))

        class FakeWriter:
            def __init__(self, path, width, height): self.path = path
            def __enter__(self): return self
            def write(self, value):
                with self.path.open("ab") as stream: stream.write(value)
            def __exit__(self, *_): pass

        class FakePipeline:
            def __init__(self, client, vehicle, output, case_id, required_observations=()):
                self.output = output
                self.frames = 0
                (output / "capture").mkdir()
                (output / "road.xodr").write_text("<OpenDRIVE/>")
                self.trace = (output / "trace.jsonl").open("x")
                self.evidence = (output / "capture/evidence.jsonl").open("x")
            def capture(self, frame, time_s):
                row = json.dumps({"frame": frame, "time_s": time_s}) + "\n"
                self.trace.write(row)
                self.evidence.write(row)
                self.frames += 1
            def close(self, confirmed=True):
                self.trace.close()
                self.evidence.close()
                (self.output / "capture/manifest.json").write_text(json.dumps(
                    {"extraction_confirmed": confirmed, "frames": self.frames}))

        @contextmanager
        def vehicles(world, context):
            yield FakeVehicle(), {"road_id": 4, "lane_id": -1, "measured_length_m": 500,
                                  "waypoints": [NS(transform=NS(location=NS(x=x, y=0))) for x in (0, 500)]}

        @contextmanager
        def cameras(world, vehicle, transforms):
            yield world.sensors

        world = FakeWorld()
        client = NS(get_world=lambda: world)
        carla = NS(Transform=lambda *args: args, Location=lambda **kw: kw,
                   Rotation=lambda **kw: kw, VehicleControl=lambda **kw: kw)
        restored = []
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp)
            short_config = config()
            short_config["duration_s"] = 1
            (output / "runner.py").write_text("fake materialized runner")
            (output / "construction.json").write_text("{}")
            (output / "config.json").write_text(json.dumps(short_config))
            with patch.dict(sys.modules, {"pipeline_capture": NS(PipelineCapture=FakePipeline)}), \
                 patch("runner.construct_vehicle", vehicles), patch("runner.source_cameras", cameras), \
                 patch("runner.FFV1Writer", FakeWriter), \
                 patch("runner.NativeDrive", lambda *args: NS(step=lambda vehicle: {"throttle": .5})), \
                 patch.object(world_restore, "snapshot", lambda client: {"saved": True}), \
                 patch.object(world_restore, "restore", lambda client, saved: restored.append(saved)):
                capture(client, carla, short_config, output)
            seal = json.loads((output / "capture-seal.json").read_text())
            self.assertEqual(seal["frame_count"], 20)
            self.assertEqual(len((output / "video_frames.jsonl").read_text().splitlines()), 20)
            self.assertEqual(len((output / "capture/evidence.jsonl").read_text().splitlines()), 20)
            self.assertEqual(len(seal["sources"]), 13)
            self.assertEqual(restored, [{"saved": True}])


if __name__ == "__main__":
    unittest.main()
