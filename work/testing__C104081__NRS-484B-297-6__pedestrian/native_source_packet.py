"""Seal synchronized Native pedestrian observations for saved-only measurement.

The caller supplies readbacks from the same world snapshot as each walking
sample. This writer never labels a fixture as original acquisition.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

from saved_measurement import REQUIRED
from native_walking import run_constructed
from native_construction import load_site_survey

STREAMS = ("video_frames.jsonl", "pedestrian_history.jsonl",
           "obstruction_history.jsonl", "traffic_history.jsonl")


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _valid_digest(value: object) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(c in "0123456789abcdef" for c in value)


class NativeSourcePacket:
    """Collect one measured world tick and its four source observations at a time."""

    def __init__(self, case_id: str, survey_path: Path, survey_sha256: str,
                 camera_profile_sha256: str, traffic_plan_sha256: str,
                 pedestrian_blueprint: str):
        raw = Path(survey_path).read_bytes()
        if _sha(raw) != survey_sha256:
            raise ValueError("Native survey digest mismatch")
        load_site_survey(Path(survey_path), survey_sha256)
        if not case_id.startswith("testing__C104081__NRS-484B-297-6__pedestrian__"):
            raise ValueError("wrong exact pedestrian case")
        if not _valid_digest(camera_profile_sha256) or not _valid_digest(traffic_plan_sha256):
            raise ValueError("source-bound camera and traffic plan digests required")
        if not isinstance(pedestrian_blueprint, str) or not pedestrian_blueprint.startswith("walker.pedestrian."):
            raise ValueError("original pedestrian blueprint identity required")
        self.case_id = case_id
        self.survey = raw
        self.context = {"pedestrian_blueprint": pedestrian_blueprint,
                        "camera_profile_sha256": camera_profile_sha256,
                        "traffic_plan_sha256": traffic_plan_sha256}
        self.rows = {name: [] for name in STREAMS}

    def observe(self, walking_sample: dict, readbacks: dict) -> None:
        """Reject stale or unsynchronized source packets before retaining them."""
        frame, time_s = walking_sample.get("frame"), walking_sample.get("time_s")
        if type(frame) is not int or type(time_s) not in (int, float) or not math.isfinite(time_s):
            raise ValueError("invalid measured Native frame/time")
        index = len(self.rows[STREAMS[0]])
        if index:
            previous = self.rows[STREAMS[0]][-1]
            if frame != previous["carla_frame"] + 1 or abs(time_s - previous["time_s"] - .05) > .001:
                raise ValueError("Native capture 20 Hz frame continuity failure")
        if set(readbacks) != set(STREAMS):
            raise ValueError("all four synchronized Native source readbacks required")
        expected = {"carla_frame": frame, "video_frame": index, "time_s": time_s}
        frozen = {}
        for name in STREAMS:
            row = readbacks[name]
            if not isinstance(row, dict):
                raise ValueError("Native source row must be an object")
            if name == "video_frames.jsonl":
                if row != expected:
                    raise ValueError("Native video map does not join measured frame/time")
            elif row.get("frame") != frame or type(row.get("time_s")) not in (int, float) or abs(row["time_s"] - time_s) > 1e-4:
                raise ValueError("Native source does not join measured frame/time")
            # Freeze each readback now: later adapter mutations cannot change a sealed row.
            frozen[name] = json.loads(json.dumps(row, allow_nan=False))
        for name in STREAMS:
            self.rows[name].append(frozen[name])

    def seal(self, output: Path) -> dict:
        """Write the original-source packet after exactly 900 contiguous ticks."""
        if any(len(rows) != 900 for rows in self.rows.values()):
            raise ValueError("900 synchronized Native frames required")
        output = Path(output)
        if output.exists() and any(output.iterdir()):
            raise ValueError("Native packet output must be empty")
        output.mkdir(parents=True, exist_ok=True)
        payloads = {"site-survey.json": self.survey}
        for name, rows in self.rows.items():
            payloads[name] = ("".join(json.dumps(row, sort_keys=True, allow_nan=False) + "\n"
                                      for row in rows)).encode()
        if set(payloads) != set(REQUIRED):
            raise ValueError("saved measurement source contract changed")
        for name, raw in payloads.items():
            (output / name).write_bytes(raw)
        packet = {"case_id": self.case_id, "source_kind": "original_saved_acquisition",
                  "capture_context": self.context,
                  "files": {name: {"path": name, "sha256": _sha(payloads[name])}
                            for name in REQUIRED}}
        (output / "source-packet.json").write_text(json.dumps(packet, indent=2) + "\n")
        return packet


def capture_constructed_sources(world, walker, carla, constructed: dict,
                                survey_path: Path, case_id: str, source_reader,
                                output: Path, *, camera_profile_sha256: str,
                                traffic_plan_sha256: str, pedestrian_blueprint: str,
                                speed_m_s: float = 1.4, camera_recorder=None,
                                on_core_sample=None) -> dict:
    """Run the measured route and read all source streams at each Native tick.

    `source_reader(sample)` must read the just-ticked Native world, including
    original body, obstacle, traffic and video-frame identity. The caller owns
    world settings, actors and cameras. The writer retains no planned positions
    as observations and does not certify visibility or legal judgments.
    """
    packet = NativeSourcePacket(case_id, survey_path, constructed.get("survey_sha256"),
                                camera_profile_sha256, traffic_plan_sha256,
                                pedestrian_blueprint)

    def observe(sample):
        packet.observe(sample, source_reader(sample))
        if on_core_sample is not None:
            on_core_sample(sample["frame"], sample["time_s"])

    try:
        run_constructed(world, walker, carla, constructed, survey_path, case_id,
                        speed_m_s=speed_m_s, on_sample=observe)
        result = packet.seal(output)
        if camera_recorder is not None:
            result["camera_media"] = camera_recorder.seal(output)
        return result
    except Exception:
        if camera_recorder is not None:
            camera_recorder.abort()
        raise
