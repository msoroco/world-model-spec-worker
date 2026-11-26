"""Capture original 20 Hz overtaking motion with four joined Native cameras.

The local adapter supplies Native snapshots and pixels. This code records them
without calling any legal predicate; later independent review remains mandatory.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

from pass_controller import Observation, command_for_case
from pass_measurements import ASSIGNMENT_ID, measure, validate_context
from pass_scene import construct


CAMERAS = ("overview", "approach", "reference_corner", "driver_reference")
FRAME_COUNT = 900


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _write_json(path, value):
    Path(path).write_text(json.dumps(value, sort_keys=True) + "\n", encoding="utf-8")


def capture(adapter, packet_path, case, destination, *, control_profile=None):
    """Record exactly 45 seconds. Failure removes the staged attempt and actors."""
    destination = Path(destination)
    if destination.exists():
        raise ValueError("original capture destination already exists")
    if getattr(adapter, "native_attested", False) is not True:
        raise ValueError("attested original Native adapter required")
    destination.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix="pass-original-", dir=destination.parent))
    owned = []
    try:
        scene = construct(adapter, packet_path, case)
        owned = scene["owned"]
        packet = scene["packet"]
        context = adapter.read_context(scene["actors"])
        if context.get("case_id") != case["case_id"] or context.get("control_kind") != packet["control_kind"]:
            raise ValueError("original context case or control identity mismatch")
        map_ref = next((r for r in packet["source_refs"] if r.get("role") == "map"), None)
        if map_ref is None or context.get("map_sha256") != map_ref["sha256"]:
            raise ValueError("original context map source mismatch")
        _, _, lane_count, immediate_left, _ = validate_context(context, case["case_id"])
        if lane_count != case["same_direction_lane_count_requested"] or immediate_left != packet["immediate_left_lane_id"]:
            raise ValueError("original context lane topology mismatch")
        context_path = stage / "original-context.json"
        _write_json(context_path, context)
        frame_dirs = {name: stage / ("frames-" + name) for name in CAMERAS}
        for folder in frame_dirs.values():
            folder.mkdir()
        trace = []
        frame_map = []
        prior = None
        for index in range(FRAME_COUNT):
            observed = adapter.observe_pass(scene["actors"])
            if not isinstance(observed, Observation):
                raise ValueError("original per-frame lane/traffic observation required")
            intent = command_for_case(case, observed)
            adapter.apply_pass_control(scene["actors"]["ego"], intent, control_profile or {})
            snapshot = adapter.tick(scene["actors"])
            frame, time_s = snapshot.get("frame"), snapshot.get("time_s")
            if type(frame) is not int or type(time_s) not in (int, float):
                raise ValueError("original Native frame and time required")
            if prior is not None and (frame != prior[0] + 1 or abs(time_s - prior[1] - .05) > .002):
                raise ValueError("original Native 20 Hz frame join failed")
            prior = frame, time_s
            row = adapter.read_pass_row(frame, scene["actors"])
            if row.get("origin") != "native_world_snapshot" or row.get("frame") != frame or row.get("time_s") != time_s:
                raise ValueError("original actor frame/time source mismatch")
            row = dict(row)
            row.pop("origin")
            if row.get("ego_lane_id") not in {r["lane_id"] for r in packet["lanes"]} or not isinstance(row.get("left_lane_occupied_actor_ids"), list):
                raise ValueError("original lane or surrounding traffic readback missing")
            row["control_intent"] = intent
            cameras = adapter.read_cameras(frame, scene["actors"])
            if not isinstance(cameras, dict) or set(cameras) != set(CAMERAS):
                raise ValueError("four original cameras required")
            hashes = {}
            for name in CAMERAS:
                image = cameras[name]
                raw = image.get("png")
                if image.get("frame") != frame or image.get("time_s") != time_s or \
                        not isinstance(raw, bytes) or not raw.startswith(b"\x89PNG\r\n\x1a\n"):
                    raise ValueError("original camera pixel/frame join failed: " + name)
                (frame_dirs[name] / f"{index:04d}.png").write_bytes(raw)
                hashes[name] = hashlib.sha256(raw).hexdigest()
            trace.append(row)
            frame_map.append({"frame": frame, "time_s": time_s, "camera_png_sha256": hashes})
        trace_path = stage / "original-trace.jsonl"
        trace_path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in trace), encoding="utf-8")
        frame_map_path = stage / "camera-frame-map.jsonl"
        frame_map_path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in frame_map), encoding="utf-8")
        receipt = {"assignment_id": ASSIGNMENT_ID,
                   "case_id": case["case_id"], "source_kind": "original_native_capture",
                   "diagnostic_fixture": False, "fps": 20, "frame_count": FRAME_COUNT,
                   "context_sha256": _sha(context_path), "trace_sha256": _sha(trace_path),
                   "frame_map_sha256": _sha(frame_map_path),
                   "reviewed_packet_sha256": _sha(packet_path),
                   "physical_acceptance": False, "legal_verdict": None}
        videos = {}
        for name, folder in frame_dirs.items():
            video = stage / (name + ".mkv")
            subprocess.run(["ffmpeg", "-v", "error", "-nostdin", "-framerate", "20",
                            "-i", str(folder / "%04d.png"), "-frames:v", str(FRAME_COUNT),
                            "-c:v", "ffv1", str(video)], check=True,
                           stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
            videos[name] = {"path": video.name, "sha256": _sha(video),
                            "frame_count": FRAME_COUNT}
            shutil.rmtree(folder)
        receipt["cameras"] = videos
        receipt_path = stage / "original-source-receipt.json"
        _write_json(receipt_path, receipt)
        measurement = measure(case_id=case["case_id"], context_path=context_path,
                              trace_path=trace_path, receipt_path=receipt_path)
        _write_json(stage / "pass-measurement.json", measurement)
        os.replace(stage, destination)
        return receipt
    except BaseException:
        shutil.rmtree(stage, ignore_errors=True)
        raise
    finally:
        try:
            adapter.brake()
        finally:
            try:
                for actor in reversed(owned):
                    adapter.destroy(actor)
            finally:
                adapter.restore()
