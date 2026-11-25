"""Original-frame acquisition loop for the signed yellow-curb freight cases.

The caller owns the CARLA world, cameras, encoder and restoration. The sample
callback must read the post-tick live ego/body/cargo state; no commanded target
is used as an observation. Each call is joined to the original Native frame.
"""

from __future__ import annotations

import json
import os
import hashlib
from pathlib import Path

from freight_contract import SourceError, VARIANTS
from saved_delivery import CAMERAS


ASSIGNMENT = "testing__C149555__LVMC-11-52-030-B__motor_vehicle_driver"


def capture_original_frames(adapter, sample, output_dir: Path, *, case_id: str, frames: int = 900,
                            frame_map_factory=None, read_camera=None,
                            native_capture=None) -> list[dict]:
    if not os.environ.get("SCENARIO_PIPELINE_OUTPUT_ROOT"):
        raise SourceError("SCENARIO_PIPELINE_OUTPUT_ROOT must route runtime output to .runtime-work")
    if case_id not in {f"{ASSIGNMENT}__{variant}" for variant in VARIANTS}:
        raise SourceError("unknown exact freight case")
    if frames != 900:
        raise SourceError("exact freight delivery requires 900 original frames")
    if (read_camera is None) != (native_capture is None):
        raise SourceError("four cameras and PipelineCapture must be synchronized together")
    if frame_map_factory is None:
        from scenario_pipeline.worker_exchange.native_output import FrameMap
        frame_map_factory = FrameMap
    output_dir = Path(output_dir)
    if not output_dir.is_dir():
        raise SourceError("original attempt directory missing")
    motion_path = output_dir / "freight_motion.jsonl"
    frame_map_path = output_dir / "frame-map.jsonl"
    frame_index_path = output_dir / "frame-index.json"
    if motion_path.exists() or frame_map_path.exists() or frame_index_path.exists():
        raise SourceError("original acquisition files already exist")
    rows = []
    camera_rows = {name: [] for name in CAMERAS}
    if read_camera is not None:
        for name in CAMERAS:
            (output_dir / "cameras" / name).mkdir(parents=True, exist_ok=False)
    with frame_map_factory(frame_map_path) as frame_map, motion_path.open("x", encoding="utf-8") as motion:
        for index in range(frames):
            control = adapter.step_capture(index)
            native_frame = adapter.world.tick()
            snapshot = adapter.world.get_snapshot()
            if snapshot.frame != native_frame:
                raise SourceError("Native snapshot/frame mismatch")
            time_s = snapshot.timestamp.elapsed_seconds
            source = sample(index, native_frame, snapshot)
            if not isinstance(source, dict):
                raise SourceError("missing original motion sample")
            if source.get("original_frame") != index:
                raise SourceError("sample/original frame mismatch")
            if source.get("native_frame") != native_frame:
                raise SourceError("sample/Native frame mismatch")
            if source.get("time_s") != time_s:
                raise SourceError("sample/Native timestamp mismatch")
            if native_capture is not None:
                captured = native_capture.capture(native_frame, time_s)
                if captured.get("frame") != native_frame or captured.get("time_s") != time_s:
                    raise SourceError("PipelineCapture/Native frame join mismatch")
                for name in CAMERAS:
                    image_frame, image_bytes = read_camera(name, native_frame)
                    if image_frame != native_frame or not isinstance(image_bytes, bytes) or \
                            not image_bytes.startswith(b"\x89PNG\r\n\x1a\n"):
                        raise SourceError("original camera frame drift or non-PNG source: " + name)
                    image_path = output_dir / "cameras" / name / f"{index:06d}.png"
                    image_path.write_bytes(image_bytes)
                    camera_rows[name].append({"original_frame": index, "native_frame": native_frame,
                                              "path": str(image_path.relative_to(output_dir)),
                                              "sha256": hashlib.sha256(image_bytes).hexdigest()})
            row = frame_map.append(native_frame, time_s,
                                   controller_phase=control["phase"])
            if row["video_frame"] != index:
                raise SourceError("original video/frame-map identity mismatch")
            motion.write(json.dumps(source, allow_nan=False) + "\n")
            rows.append(source)
    if adapter.phase not in ("hold", "complete"):
        raise SourceError("freight motion did not complete within original capture")
    frame_index_path.write_text(json.dumps({"case_id": case_id,
                                            "frames": [row["original_frame"] for row in rows]},
                                           separators=(",", ":")) + "\n", encoding="utf-8")
    if read_camera is not None:
        for name, images in camera_rows.items():
            path = output_dir / (name + "-camera.jsonl")
            path.write_text("".join(json.dumps(image, separators=(",", ":")) + "\n"
                                    for image in images), encoding="utf-8")
    return rows
