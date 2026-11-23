"""Original 20 Hz Native condition, controller and camera-frame acquisition.

The caller supplies a reviewed scene, four-view rig and owns world restoration.
Raw media and trace stay under .runtime-work until saved processing closes them.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

from native_conditions import NativeConditionCapture
from native_control import step


VIEWS = ("overview", "approach", "reference_corner", "driver_reference")


def _point(actor):
    location = actor.get_transform().location
    values = (location.x, location.y, location.z)
    if any(isinstance(value, bool) or not isinstance(value, (int, float)) or
           not math.isfinite(value) for value in values):
        raise ValueError("original Native actor position invalid")
    return list(values)


def _source_root(attempt: Path):
    root = Path(__file__).resolve().parents[2] / ".runtime-work"
    attempt = Path(attempt).resolve()
    if root not in attempt.parents:
        raise ValueError("original Native output must be under .runtime-work")
    return attempt


def capture(world, scene, camera_rig, attempt: Path, case_id: str, control_factory,
            *, frame_map_factory=None, count: int = 900) -> dict:
    """Retain one fresh attempt; every tick joins condition, control and four views."""
    if count != 900:
        raise ValueError("exact 45-second capture requires 900 Native ticks")
    settings = world.get_settings()
    if (settings.synchronous_mode is not True or settings.no_rendering_mode is not False or
            not isinstance(settings.fixed_delta_seconds, (int, float)) or
            abs(settings.fixed_delta_seconds - .05) > 1e-9):
        raise ValueError("rendered synchronous 20 Hz Native world required")
    attempt = _source_root(attempt)
    if attempt.exists() and any(path.name != "raw" for path in attempt.iterdir()):
        raise ValueError("retain previous original Native attempt")
    if (attempt / "raw").exists() and camera_rig.output_root != attempt / "raw":
        raise ValueError("original camera output root differs from attempt")
    attempt.mkdir(parents=True, exist_ok=True)
    if frame_map_factory is None:
        from worker_exchange.native_output import FrameMap
        frame_map_factory = FrameMap
    conditions = NativeConditionCapture(attempt, case_id)
    previous = None
    with frame_map_factory(attempt / "video_frames.jsonl") as mapping:
        with (attempt / "trace.jsonl").open("x", encoding="utf-8") as trace:
            for index in range(count):
                tick_frame = world.tick()
                snapshot = world.get_snapshot()
                if snapshot.frame != tick_frame:
                    raise ValueError("Native tick and snapshot frame differ")
                row = conditions.append(world, scene.ego, scene.leader, snapshot)
                if previous is not None and (row["frame"] != previous[0] + 1 or
                                             not .049 <= row["time_s"] - previous[1] <= .051):
                    raise ValueError("original Native capture cadence differs")
                previous = (row["frame"], row["time_s"])
                cameras = camera_rig.await_frame(row["frame"], row["time_s"])
                if set(cameras) != set(VIEWS):
                    raise ValueError("original four-view frame set incomplete")
                for name, image in cameras.items():
                    if image.get("frame") != row["frame"] or abs(image.get("time_s", -1) - row["time_s"]) > .05:
                        raise ValueError("original camera and Native frame join differs")
                    if not image.get("sha256") or not image.get("raw_bgra"):
                        raise ValueError("original camera source reference missing")
                decision = step(scene, row, control_factory)
                trace_row = {"frame": row["frame"], "time_s": row["time_s"],
                             "source_frame": row["source_frame"],
                             "position_m": _point(scene.ego),
                             "leader_position_m": _point(scene.leader),
                             "condition_sample_index": index,
                             "camera_sources": cameras,
                             "control": decision,
                             "source_packet_sha256": scene.source["packet_sha256"],
                             "physical_acceptance_claimed": False}
                trace.write(json.dumps(trace_row, sort_keys=True, allow_nan=False) + "\n")
                mapping.append(row["frame"], row["time_s"],
                               camera_source_sha256={name: cameras[name]["sha256"] for name in VIEWS})
    seal = conditions.close()
    return {"case_id": case_id, "frames": count,
            "first_frame": seal["first_frame"], "last_frame": seal["last_frame"],
            "condition_sha256": seal["sha256"],
            "source_packet_sha256": scene.source["packet_sha256"],
            "trace_reference": "trace.jsonl", "video_frame_map_reference": "video_frames.jsonl",
            "legal_judgment": "unresolved", "physical_acceptance_claimed": False}
