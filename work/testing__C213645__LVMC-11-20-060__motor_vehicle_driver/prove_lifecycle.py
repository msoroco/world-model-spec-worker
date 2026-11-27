"""Fake Native ownership test for exact-case capture/cleanup/finalize order."""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import subprocess
import sys
import types
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
SCRATCH = REPO / ".runtime-work/c213645-owner"
EXPECTED = ["capture_finished", "encoders_closed", "restoration_verified",
            "native_exit", "owner_released", "saved_processing_started"]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", required=True)
    case_id = parser.parse_args().case
    attempt = SCRATCH / ("lifecycle-" + case_id.split("__")[-1])
    if attempt.exists():
        import shutil
        shutil.rmtree(attempt)
    command = [sys.executable, str(REPO / "runtime.py"), "materialize", "--manifest",
               str(HERE / "execution-manifest.json"), "--case", case_id, "--output", str(attempt)]
    subprocess.run(command, cwd=REPO, check=True, stdout=subprocess.DEVNULL)
    events = []

    class Session:
        def __init__(self):
            self.client = object()
            self.actors = {"ego": object()}
            self.closed = False
            self.restored = False
            self.capture_complete = False
            self.pipeline_capture = None

        def cleanup(self):
            if self.closed:
                return
            if not self.capture_complete:
                raise ValueError("capture was not completed before cleanup")
            self.pipeline_capture.close()
            self.restored = True
            events.extend(["restoration_verified", "native_exit", "owner_released"])
            self.closed = True

    session = Session()

    class PipelineCapture:
        def __init__(self, client, ego, output, case):
            assert case == case_id

        def capture(self, frame):
            pass

        def close(self):
            events.append("encoders_closed")

    fake_adapter = types.ModuleType("carla_driveway_adapter")
    fake_adapter.open_session = lambda case, packet, host, port, spawn_offset_m=0: session
    fake_acquisition = types.ModuleType("native_acquisition")
    fake_acquisition.capture = lambda session, case, output, after_tick: events.append("capture_finished")
    fake_capture = types.ModuleType("pipeline_capture")
    fake_capture.PipelineCapture = PipelineCapture
    fake_finalizer = types.ModuleType("finalize_native")

    def finalize(output, case_id, restored):
        if not session.closed or not restored:
            raise ValueError("saved processing began before Native owner release")
        events.append("saved_processing_started")

    fake_finalizer.finalize = finalize
    sys.modules.update(carla_driveway_adapter=fake_adapter, native_acquisition=fake_acquisition,
                       pipeline_capture=fake_capture, finalize_native=fake_finalizer)
    spec = importlib.util.spec_from_file_location("driveway_lifecycle_runner", attempt / "runner.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    old_argv = sys.argv
    try:
        sys.argv = ["runner.py", "--output-dir", str(attempt), "--packet", str(SCRATCH / "reviewed-packet.json")]
        module.main()
    finally:
        sys.argv = old_argv
    if events != EXPECTED:
        raise ValueError("Native lifecycle order differs: " + json.dumps(events))
    print(" ".join(events))


if __name__ == "__main__":
    main()
