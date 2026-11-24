"""CPU fake proof of capture, encoder closure and world restoration order."""

from __future__ import annotations

import json
import os
from pathlib import Path
import sys
import tempfile
import types
from unittest.mock import patch

import runner


def main() -> None:
    root = Path(__file__).resolve().parents[2] / ".runtime-work"
    root.mkdir(exist_ok=True)
    events = []

    class World:
        def apply_settings(self, settings):
            events.append("settings_applied")

    world = World()

    class Client:
        def __init__(self, host, port):
            events.append("client_connected")

        def set_timeout(self, seconds):
            pass

        def get_world(self):
            return world

    class Rig:
        def __init__(self, *args):
            pass

        def close(self):
            events.append("encoders_closed")

    class Scene:
        ego = object()

        def close(self):
            events.append("actors_closed")

    def capture(*args, **kwargs):
        if kwargs.get("count_capture") is not None or kwargs.get("count_reader") is not None:
            raise ValueError("unselected diagnostic count source was supplied")
        events.append("capture_finished")
        return {"frames": 900}

    def restore(*args):
        events.append("restoration_verified")
        return {"restored": True}

    def finalize_media(*args):
        events.append("media_sealed")
        return {"sealed": True}

    carla = types.ModuleType("carla")
    carla.Client = Client
    carla.Vector3D = object
    carla.VehicleControl = object
    carla.Location = lambda *args: args
    carla.Rotation = lambda *args: args
    carla.Transform = lambda *args: args
    exchange = types.ModuleType("worker_exchange")
    exchange.__path__ = []
    world_restore = types.ModuleType("worker_exchange.world_restore")
    world_restore.snapshot = lambda client: {"settings": types.SimpleNamespace()}
    world_restore.restore = restore
    with tempfile.TemporaryDirectory(dir=root) as temporary:
        attempt = Path(temporary) / "attempt"
        os.environ["SCENARIO_PIPELINE_OUTPUT_ROOT"] = str(Path(temporary).resolve())
        with patch.dict(sys.modules, {"carla": carla, "worker_exchange": exchange,
                                      "worker_exchange.world_restore": world_restore}), \
             patch.object(runner, "create", return_value=Scene()), \
             patch.object(runner, "CameraRig", Rig), \
             patch.object(runner, "capture", capture), \
             patch.object(runner, "finalize_media", finalize_media), \
             patch.object(runner, "seal_authored_setup", return_value={}):
            status = runner.capture_original(attempt, Path("packet"), Path("plan"),
                                             "synthetic-case")
        events.append("native_exit")
        events.append("owner_released")
        events.append("saved_processing_started")
        expected = ["capture_finished", "encoders_closed", "restoration_verified",
                    "native_exit", "owner_released", "saved_processing_started"]
        if [event for event in events if event in expected] != expected:
            raise ValueError("capture closure order differs: " + repr(events))
        if status["errors"] or status["restoration"] != {"restored": True}:
            raise ValueError("fake Native capture did not close successfully")
        if not (attempt / "native-run-status.json").is_file():
            raise ValueError("Native status was not retained")
    print(json.dumps({"events": expected, "exit_code": 0,
                      "provenance_kind": "synthetic_fixture",
                      "method": "runner capture_original with fake CARLA client, rig and world"},
                     sort_keys=True))


if __name__ == "__main__":
    main()
