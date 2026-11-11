"""Join PipelineCapture, fire-specific sources and frame mapping on each live tick.

The runner owns the world, cameras and PipelineCapture lifecycle. This adapter
owns only the two fire sources, original frame map and authored context file.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path


def _load_local(name):
    path = Path(__file__).with_name(name + ".py")
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


FireSourceRecorder = _load_local("fire_source_capture").FireSourceRecorder


class FireCaptureSession:
    def __init__(self, output, pipeline_capture, ego, apparatus, context):
        from scenario_pipeline.worker_exchange.native_output import FrameMap

        output = Path(output)
        if not isinstance(context, dict) or not context.get("alarm_response_source"):
            raise ValueError("Alarm dispatch premise requires a source")
        for name in ("apparatus_answered_alarm", "subject_authorized_emergency",
                     "subject_official_business"):
            if type(context.get(name)) is not bool:
                raise ValueError("Fire exception and alarm premises require booleans")
        if (output / "fire_context.json").exists():
            raise ValueError("Retain prior fire context; use a fresh attempt")
        self.pipeline = pipeline_capture
        self.context = output / "fire_context.json"
        self.context.write_text(json.dumps(context, indent=2, allow_nan=False) + "\n")
        self.fire = FireSourceRecorder(output, ego, apparatus)
        try:
            self.frames = FrameMap(output / "video_frames.jsonl")
        except BaseException:
            self.fire.close()
            raise
        self.closed = False

    def capture(self, frame, time_s, *, warning_lamp_readback, siren_readback):
        if self.closed:
            raise ValueError("Fire capture session is closed")
        if type(warning_lamp_readback) is not bool or siren_readback is not None and type(siren_readback) is not bool:
            raise ValueError("Warning lamp requires a Native readback; siren must be a readback or unknown")
        # PipelineCapture verifies the current world snapshot and writes the
        # original trace/graphs. FireSourceRecorder then records the same tick.
        row = self.pipeline.capture(frame, time_s)
        if row.get("frame") != frame or row.get("time_s") != time_s:
            raise ValueError("Pipeline capture returned another original tick")
        self.fire.append(frame, time_s,
                         warning_lamp_readback=warning_lamp_readback,
                         siren_readback=siren_readback)
        self.frames.append(frame, time_s)
        return row

    def close(self):
        if not self.closed:
            self.closed = True
            self.frames.close()
            self.fire.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()
