"""Publish one sealed, same-frame original pedestrian attempt to Core.

The caller owns live capture and restoration. This step refuses missing graphs,
trace rows, pixels, or a changed pedestrian source packet. It records no legal
conclusion and leaves independent physical review to delivery acceptance.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from delivery_audit import audit_saved
from saved_finalizer import build_result


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line]


def verify_core_join(root, case_id, expected_frames=900):
    root = Path(root).resolve()
    packet = json.loads((root / "source-packet.json").read_text())
    if packet.get("case_id") != case_id or packet.get("source_kind") != "original_saved_acquisition":
        raise ValueError("original pedestrian source packet required")
    manifest = json.loads((root / "capture/manifest.json").read_text())
    if (manifest.get("case_id") != case_id or
            manifest.get("acquisition") != "original_live_run" or
            manifest.get("frames") != expected_frames or
            manifest.get("extraction_confirmed") is not True):
        raise ValueError("complete live Core graph capture required")
    names = ("trace.jsonl", "capture/evidence.jsonl", "capture/native/frames.jsonl",
             "video_frames.jsonl", "pedestrian_history.jsonl")
    streams = [_rows(root / name) for name in names]
    if any(len(rows) != expected_frames for rows in streams):
        raise ValueError("Core and pedestrian source frame counts differ")
    for index, (trace, evidence, graph, video, pedestrian) in enumerate(zip(*streams)):
        frame = video.get("carla_frame")
        when = video.get("time_s")
        if (type(frame) is not int or frame != trace.get("frame") or
                frame != evidence.get("original_frame") or frame != graph.get("frame") or
                frame != pedestrian.get("frame") or video.get("video_frame") != index or
                any(abs(value - when) > .001 for value in
                    (trace.get("time_s", -1), evidence.get("recording_time_s", -1),
                     pedestrian.get("time_s", -1)))):
            raise ValueError("same-frame Core, graph, video, pedestrian join differs")
        if index and frame != streams[3][index - 1]["carla_frame"] + 1:
            raise ValueError("original Core graph frame gap")
        ref = graph.get("adapter_graph")
        if not isinstance(ref, str):
            raise ValueError("live Core adapter graph missing")
        path = (root / "capture/native" / ref).resolve()
        if not path.is_relative_to((root / "capture/native").resolve()) or not path.is_file():
            raise ValueError("live Core adapter graph path invalid")
        payload = json.loads(path.read_text())
        if (payload.get("format") != "native-adapter-graph-v1" or
                payload.get("metadata", {}).get("frame") != frame or
                not isinstance(payload.get("nodes"), list) or
                not isinstance(payload.get("edges"), list)):
            raise ValueError("live Core adapter graph structure differs")
    if _sha(root / "trace.jsonl") != manifest.get("sources", {}).get("trace.jsonl"):
        raise ValueError("Core trace source hash differs")
    if _sha(root / "road.xodr") != manifest.get("sources", {}).get("road.xodr"):
        raise ValueError("Core map source hash differs")
    return {"frame_count": expected_frames,
            "core_manifest_sha256": _sha(root / "capture/manifest.json"),
            "source_packet_sha256": _sha(root / "source-packet.json")}


def publish_original(root, case_id):
    from worker_exchange.native_output import (
        physical_result, seal_capture, validate_result, write_result)
    root = Path(root).resolve()
    joined = verify_core_join(root, case_id)
    audit = audit_saved(root, case_id, decode_media=True)
    if not audit["checks"]["native_source"] or not audit["checks"]["full_video_decode"]:
        raise ValueError("original full-decode saved audit required")
    lifecycle = json.loads((root / "lifecycle-receipt.json").read_text())
    if lifecycle.get("world_restore", {}).get("restored") is not True:
        raise ValueError("verified world restoration required before publication")
    result = build_result(root, case_id, decode_media=True)
    result["trace_reference"] = "trace.jsonl"
    result = physical_result(root, result)
    validate_result(result)
    if (root / "result.json").exists() or (root / "capture-seal.json").exists():
        raise ValueError("prior Native publication exists")
    (root / "acquisition-provenance.json").write_text(json.dumps({
        "provenance_kind": "native", "diagnostic_fixture": False,
        "capture_manifest_sha256": joined["core_manifest_sha256"],
        "source_packet_sha256": joined["source_packet_sha256"]}, indent=2) + "\n")
    write_result(root, result)
    seal_capture(root, frames=joined["frame_count"],
                 restoration=lifecycle["world_restore"], errors=[],
                 encoder_exit_codes={name: 0 for name in audit["sealed_camera_media"]},
                 context={"case_id": case_id, "core_manifest_sha256": joined["core_manifest_sha256"],
                          "source_packet_sha256": joined["source_packet_sha256"]})
    return joined
