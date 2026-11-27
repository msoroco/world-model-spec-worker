"""Exercise Native acquisition and cleanup with a controlled CARLA API stub.

This never creates a recording or a physically accepted result.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from types import ModuleType, SimpleNamespace
import shutil

import runner
from capture_plan import build
from geometry import open_drive
from original_source_contract import CAMERAS, REVIEW_FINDINGS, sha, validate


class Blueprint:
    def __init__(self, name):
        self.id = name

    def set_attribute(self, key, value):
        pass


class Library:
    def find(self, name):
        return Blueprint(name)

    def filter(self, pattern):
        return [Blueprint("walker.pedestrian.001")]


class Actor:
    next_id = 1

    def __init__(self, blueprint, transform, world):
        self.id = Actor.next_id
        Actor.next_id += 1
        self.type_id = blueprint.id
        self.transform = transform
        self.world = world
        self.bounding_box = SimpleNamespace(extent=SimpleNamespace(x=2.0, y=0.8))
        self.callback = None
        self.destroyed = False

    def listen(self, callback):
        self.callback = callback
        self.world.cameras.append(self)

    def apply_control(self, control):
        pass

    def get_transform(self):
        return self.transform

    def get_velocity(self):
        return SimpleNamespace(x=0.0, y=0.0, z=0.0)

    def get_location(self):
        return self.transform.location

    def open_door(self, door):
        pass

    def stop(self):
        pass

    def destroy(self):
        self.destroyed = True


class World:
    def __init__(self):
        self.settings = SimpleNamespace(synchronous_mode=False)
        self.cameras = []
        self.actors = []
        self.frame = 0

    def get_actors(self):
        return self.actors

    def get_settings(self):
        return self.settings

    def apply_settings(self, settings):
        self.settings = settings

    def get_map(self):
        return SimpleNamespace(to_opendrive=open_drive)

    def get_blueprint_library(self):
        return Library()

    def spawn_actor(self, blueprint, transform):
        actor = Actor(blueprint, transform, self)
        self.actors.append(actor)
        return actor

    def try_spawn_actor(self, blueprint, transform):
        return self.spawn_actor(blueprint, transform)

    def tick(self):
        self.frame += 1
        for camera in self.cameras:
            camera.callback(SimpleNamespace(frame=self.frame, raw_data=b"stub-pixel"))
        return self.frame

    def get_snapshot(self):
        return SimpleNamespace(frame=self.frame)


class Client:
    latest = None

    def __init__(self, host, port):
        self.prior = World()
        self.world = None
        self.restored = False
        Client.latest = self

    def set_timeout(self, seconds):
        pass

    def get_world(self):
        return self.prior

    def generate_opendrive_world(self, xml, parameters):
        assert xml == open_drive()
        self.world = World()
        return self.world


class Encoder:
    def __init__(self, args, stdin, stderr):
        self.path = Path(args[-1])
        self.returncode = None
        self.stdin = self
        self.stderr = SimpleNamespace(read=lambda: b"")
        self.frames = 0

    def write(self, data):
        self.frames += 1

    def close(self):
        self.path.write_bytes(b"controlled-placeholder-video")

    def wait(self, timeout=None):
        assert self.frames == 600
        self.returncode = 0
        return 0

    def poll(self):
        return self.returncode

    def kill(self):
        self.returncode = -9


def prove() -> dict:
    carla = ModuleType("carla")
    carla.Client = Client
    carla.Location = lambda **kw: SimpleNamespace(
        **kw, distance=lambda other: ((kw["x"] - other.x) ** 2 +
                                       (kw["y"] - other.y) ** 2) ** .5)
    carla.Rotation = lambda **kw: SimpleNamespace(**kw)
    carla.Transform = lambda location, rotation=None: SimpleNamespace(
        location=location, rotation=rotation or SimpleNamespace(yaw=0))
    carla.VehicleControl = lambda **kw: SimpleNamespace(**kw)
    carla.VehicleDoor = SimpleNamespace(FR="front_right")
    carla.OpendriveGenerationParameters = lambda **kw: SimpleNamespace(**kw)
    package = ModuleType("worker_exchange")
    package.__path__ = [str(Path(__file__).resolve().parents[3] /
                            "runtime/scenario_pipeline/worker_exchange")]
    capture_module = ModuleType("pipeline_capture")
    class StubPipelineCapture:
        def __init__(self, client, ego, output, case, required_observations):
            self.frames = 0
        def capture(self, frame, time_s):
            self.frames += 1
        def close(self, confirmed):
            if confirmed:
                assert self.frames == 600
    capture_module.PipelineCapture = StubPipelineCapture
    world_restore = ModuleType("worker_exchange.world_restore")
    world_restore.snapshot = lambda client: {
        "settings": SimpleNamespace(synchronous_mode=False)}

    def restore(client, saved):
        client.restored = True
        return {"restored": True}

    world_restore.restore = restore
    originals = {key: sys.modules.get(key) for key in
                 ("carla", "pipeline_capture", "worker_exchange", "worker_exchange.world_restore")}
    original_popen = runner.subprocess.Popen
    scratch = Path(os.environ.get("TMPDIR", ".runtime-work")).resolve()
    scratch.mkdir(parents=True, exist_ok=True)
    try:
        sys.modules.update({"carla": carla, "pipeline_capture": capture_module,
                            "worker_exchange": package,
                            "worker_exchange.world_restore": world_restore})
        runner.subprocess.Popen = Encoder
        with tempfile.TemporaryDirectory(prefix="c135709-native-stub-", dir=scratch) as temp:
            attempt = Path(temp)
            pkg = Path(__file__).resolve().parent.parent
            shutil.copy2(pkg / "native/runner.py", attempt / "runner.py")
            shutil.copy2(pkg / "cases/exception_1_2/construction.json",
                         attempt / "construction.json")
            shutil.copy2(pkg / "cases/exception_1_2/config.json", attempt / "config.json")
            result = runner.execute(build("exception_1_2"), attempt, "127.0.0.1", 2000)
            manifest = json.loads((attempt / "capture-manifest.json").read_text())
            actors = [json.loads(line) for line in
                      (attempt / "actor-frames.jsonl").read_text().splitlines()]
            joins = [json.loads(line) for line in
                     (attempt / "camera-frames.jsonl").read_text().splitlines()]
            assert len(actors) == len(joins) == 600
            assert manifest["closed"] and manifest["world_restored"]
            assert all(joins[i]["native_frame"] == actors[i]["native_frame"]
                       for i in range(600))
            assert all(len(row["cameras"]) == 4 for row in joins)
            assert Client.latest.restored
            assert all(actor.destroyed for actor in Client.latest.world.actors)
            assert result["legal_conclusion"] is None
            runner.subprocess.Popen = original_popen
            for name in CAMERAS:
                subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i",
                                "color=c=black:s=64x48:r=20", "-frames:v", "600",
                                "-c:v", "ffv1", "-y", str(attempt / f"{name}.mkv")],
                               check=True, capture_output=True)
                manifest["video_sources"][name]["sha256"] = sha(attempt / f"{name}.mkv")
            (attempt / "capture-manifest.json").write_text(
                json.dumps(manifest, sort_keys=True) + "\n", encoding="utf-8")
            (attempt / "capture-seal.json").unlink()
            from worker_exchange.native_output import seal_capture
            from worker_exchange.saved_processing import record_native_exit
            seal_capture(attempt, frames=600, restoration={"restored": True}, errors=[],
                         encoder_exit_codes={name: 0 for name in CAMERAS})
            record_native_exit(attempt)
            source_names = ("capture-manifest.json", "road.xodr", "zone-survey.json",
                            "actor-frames.jsonl", "camera-frames.jsonl", "trace.jsonl",
                            "video_frames.jsonl", "capture-seal.json") + tuple(
                                f"{name}.mkv" for name in CAMERAS)
            review_path = attempt / "source-review.json"
            review_path.write_text(json.dumps({
                "case_id": result["case_id"],
                "source_sha256": {name: sha(attempt / name) for name in source_names},
                "reviewer": "controlled-fixture", "restricted_purpose": "test_purpose",
                "sign_authority": "unverified", "sign_pixel_status": "unverified",
                "original_findings": {name: {"status": "unverified", "source_refs": []}
                                      for name in REVIEW_FINDINGS}},
                sort_keys=True) + "\n", encoding="utf-8")
            source_result = validate(attempt, review_path)
            assert source_result["case_id"] == result["case_id"]
            assert source_result["frame_count"] == 600
            return {"format": "restricted-zone-native-stub-proof-v1",
                    "case_id": result["case_id"], "actor_frames": len(actors),
                    "four_camera_joins": len(joins), "world_restored": True,
                    "owned_actors_destroyed": True, "carla_executed": False,
                    "videos_are_controlled_synthetic": True,
                    "source_contract_passed_after_ffv1_conversion": True,
                    "physical_acceptance_claimed": False}
    finally:
        runner.subprocess.Popen = original_popen
        for key, value in originals.items():
            if value is None:
                sys.modules.pop(key, None)
            else:
                sys.modules[key] = value


if __name__ == "__main__":
    print(json.dumps(prove(), sort_keys=True))
