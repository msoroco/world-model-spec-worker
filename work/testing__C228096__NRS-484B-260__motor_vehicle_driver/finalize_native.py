"""Seal one original private-way capture after checking every source join."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil

from private_way_construction import ASSIGNMENT, CASES
from private_way_motion import measure


CAMERAS = ("overview", "approach", "reference_corner", "driver_reference")


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def finalize(attempt, observed=None):
    from worker_exchange.native_output import FrameMap, seal_capture

    attempt = Path(attempt).resolve()
    source = attempt / "original-attempt"
    inventory = json.loads((source / "inventory.json").read_text())
    case_id = inventory.get("case_id")
    if not isinstance(case_id, str) or not case_id.startswith(ASSIGNMENT + "__") or \
            case_id.removeprefix(ASSIGNMENT + "__") not in CASES:
        raise ValueError("original private-way case identity missing")
    if inventory.get("source_kind") != "original_native" or \
            inventory.get("frame_count") != 900 or \
            inventory.get("physical_acceptance_claimed") is not False:
        raise ValueError("full original Native capture required for sealing")
    measured = measure(source, case_id)
    if measured["diagnostic_fixture"] or measured["frame_count"] != 900:
        raise ValueError("diagnostic private-way attempt cannot be sealed as Native")
    if observed is not None and observed != measured:
        raise ValueError("original motion changed between capture and sealing")
    root = Path(__file__).resolve().parent
    for name in ("config.json", "construction.json", "runner.py", "analysis.py"):
        destination = attempt / name
        expected = root / name
        if destination.exists():
            if _sha(destination) != _sha(expected):
                raise ValueError("materialized private-way source differs: " + name)
        else:
            shutil.copy2(expected, destination)
    config = json.loads((attempt / "config.json").read_text())
    if config.get("selected_case_id") != case_id:
        raise ValueError("materialized private-way case differs from Native capture")
    frame_map = json.loads((source / "frame-map.json").read_text())
    frames = frame_map.get("frames")
    if frame_map.get("case_id") != case_id or not isinstance(frames, list) or \
            len(frames) != 900 or _sha(source / "frame-map.json") != inventory.get("frame_map_sha256"):
        raise ValueError("original Native frame map incomplete")
    with FrameMap(attempt / "video_frames.jsonl") as stream:
        for index, row in enumerate(frames):
            if row.get("frame") != index or type(row.get("native_frame")) is not int:
                raise ValueError("original Native frame index differs")
            stream.append(row["native_frame"], row["native_time_s"])
    history = [json.loads(line) for line in (source / "motion.jsonl").read_text().splitlines()]
    if len(history) != 900:
        raise ValueError("original Native motion history incomplete")
    with (attempt / "trace.jsonl").open("x") as stream:
        for frame, row in zip(frames, history):
            if row.get("native_frame") != frame["native_frame"] or \
                    row.get("time_s") != frame["native_time_s"]:
                raise ValueError("original motion/frame identities differ")
            stream.write(json.dumps({"frame": row["native_frame"],
                                     "time_s": row["time_s"],
                                     "ego_on_highway": row["ego_on_highway"],
                                     "ego_speed_mps": row["ego_speed_mps"]}) + "\n")
    media = inventory.get("media", {})
    for name in (*CAMERAS, "raw"):
        entry = media.get(name)
        original = source / (name + ".mkv")
        if not isinstance(entry, dict) or entry.get("path") != name + ".mkv" or \
                _sha(original) != entry.get("sha256"):
            raise ValueError("original four-view media changed: " + name)
        shutil.copy2(original, attempt / (name + ".mkv"))
    (attempt / "acquisition-provenance.json").write_text(json.dumps({
        "provenance_kind": "native", "diagnostic_fixture": False,
        "source_kind": "original_native", "original_inventory_sha256": _sha(source / "inventory.json"),
        "physical_acceptance_claimed": False}, sort_keys=True) + "\n")
    sealed = seal_capture(attempt, frames=900,
                          restoration={"restored": True,
                                       "method": "owned Native actors and sensors; settings readback"},
                          errors=[], encoder_exit_codes={name: 0 for name in (*CAMERAS, "raw")},
                          context={"original_inventory_sha256": _sha(source / "inventory.json"),
                                   "legal_yield_judgment": "unresolved"})
    return {"case_id": case_id, "capture_seal_sha256": _sha(attempt / "capture-seal.json"),
            "source_digest": sealed["source_digest"], "physical_acceptance_claimed": False}
