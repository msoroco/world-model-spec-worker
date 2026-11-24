"""Publish source-joined alley capture to the pinned Native handoff format.

The graph/evidence files come from PipelineCapture during the original ticks.
This module only closes media and writes the result after those sources exist.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path


VIEWS = {
    "overview": ("overview", 1920, 1080),
    "alley_approach": ("approach", 1280, 720),
    "access_aisle": ("reference_corner", 1280, 720),
    "driver_reference": ("driver_reference", 1280, 720),
}


def _rows(path: Path) -> list[dict]:
    if not path.is_file() or path.is_symlink():
        raise ValueError("Missing original capture source: " + str(path.name))
    return [json.loads(line) for line in path.read_text().splitlines() if line]


def _hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def publish_original(output: Path, case_id: str, *, expected_frames: int = 900,
                     encoder=subprocess.run) -> dict:
    """Close four videos and result from a complete PipelineCapture original run."""
    from worker_exchange.native_output import FrameMap, physical_result, validate_result, write_result
    from worker_exchange.media import audit

    output = Path(output).resolve()
    original = json.loads((output / "capture.json").read_text())
    if original.get("case_id") != case_id or original.get("duration_frames") != expected_frames:
        raise ValueError("Alley original capture identity or frame count differs")
    capture_root = output / "capture"
    pipeline = json.loads((capture_root / "manifest.json").read_text())
    if pipeline.get("case_id") != case_id or pipeline.get("frames") != expected_frames or pipeline.get("extraction_confirmed") is not True:
        raise ValueError("PipelineCapture original graph/evidence run is incomplete")
    sources = {
        "trace": _rows(output / "trace.jsonl"),
        "ego": _rows(output / "ego.jsonl"),
        "context": _rows(output / "context.jsonl"),
        "operation": _rows(output / "operation.jsonl"),
        "camera": _rows(output / "camera-frame-map.jsonl"),
        "evidence": _rows(capture_root / "evidence.jsonl"),
        "graphs": _rows(capture_root / "native/frames.jsonl"),
    }
    if any(len(rows) != expected_frames for rows in sources.values()):
        raise ValueError("Original trace, graph, context or camera frame count differs")
    for index in range(expected_frames):
        frame = sources["ego"][index]["native_frame"]
        time_s = sources["ego"][index]["native_time_s"]
        if (sources["trace"][index].get("frame") != frame or
                sources["context"][index].get("native_frame") != frame or
                sources["evidence"][index].get("original_frame") != frame or
                sources["graphs"][index].get("frame") != frame or
                sources["operation"][index].get("frame") != index):
            raise ValueError("Original frame identities differ")
        if sources["camera"][index].get("native_frame") != frame:
            raise ValueError("Original camera frame differs")
        if (abs(sources["trace"][index]["time_s"] - time_s) > .001 or
                abs(sources["context"][index].get("native_time_s", -1) - time_s) > .001 or
                abs(sources["camera"][index].get("native_time_s", -1) - time_s) > .001):
            raise ValueError("Original trace timestamp differs")
        graph_ref = sources["graphs"][index].get("adapter_graph")
        if not isinstance(graph_ref, str):
            raise ValueError("Original adapter graph reference missing")
        graph_path = (capture_root / "native" / graph_ref).resolve()
        if not graph_path.is_relative_to((capture_root / "native").resolve()) or not graph_path.is_file():
            raise ValueError("Original adapter graph source missing")
        graph = json.loads(graph_path.read_text())
        if (graph.get("format") != "native-adapter-graph-v1" or
                graph.get("metadata", {}).get("frame") != frame or
                not isinstance(graph.get("nodes"), list) or not isinstance(graph.get("edges"), list)):
            raise ValueError("Original adapter graph identity or structure differs")
    mapping = output / "video_frames.jsonl"
    with FrameMap(mapping) as frame_map:
        for index, row in enumerate(sources["camera"]):
            frame_map.append(row["native_frame"], row["native_time_s"])
    from PIL import Image
    for source_name, (video_name, width, height) in VIEWS.items():
        for index in range(expected_frames):
            image = output / "camera-png" / f"{index:04d}-{source_name}.png"
            with Image.open(image) as picture:
                picture.load()
                if picture.size != (width, height):
                    raise ValueError("Original camera dimensions differ: " + source_name)
            if _hash(image) != sources["camera"][index]["cameras"][source_name]["sha256"]:
                raise ValueError("Original camera pixel hash differs: " + source_name)
        video = output / (video_name + ".mkv")
        if video.exists():
            raise ValueError("Original camera video already exists: " + video.name)
        encoder(["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-threads", "4",
                 "-framerate", "20", "-i", str(output / "camera-png" / ("%04d-" + source_name + ".png")),
                 "-c:v", "ffv1", str(video)], check=True)
        audit(video, expected_frames, mapping_sha256=_hash(mapping))
    recording = json.loads((output / "construction.json").read_text())["recording_description"]
    result = {
        "case_id": case_id,
        "measured_values": {"operation_frames": expected_frames,
                            "attention_state": "unobserved", "legal_judgment": "unresolved"},
        "target_checks": [{"target": "source-bound alley operation", "requested": True,
                           "measured": len(sources["operation"]) == expected_frames,
                           "method": "original same-frame operation and PipelineCapture join",
                           "tolerance": 0, "matched": len(sources["operation"]) == expected_frames,
                           "physical_cause_confirmed": False,
                           "cause_evidence": {"operation.jsonl": _hash(output / "operation.jsonl"),
                                              "capture/evidence.jsonl": _hash(capture_root / "evidence.jsonl")}}],
        "setup_confirmed": False, "behavior_attempted": False,
        "maneuver_completed": False,
        "termination_reason": "Native original capture ended; physical and legal review pending",
        "physical_failure_flags": [], "trace_reference": "trace.jsonl",
        "video_references": [name + ".mkv" for name in ("overview", "approach", "reference_corner", "driver_reference")],
        "video_frame_map_reference": mapping.name,
        "recording_description": recording, "recording_evidence": [],
        "realized_observables": {},
    }
    (output / "acquisition-provenance.json").write_text(json.dumps({
        "provenance_kind": "native", "diagnostic_fixture": original["diagnostic_fixture"],
        "source": "PipelineCapture joined to exact alley acquisition",
        "capture_manifest_sha256": _hash(capture_root / "manifest.json")}, sort_keys=True) + "\n")
    result = physical_result(output, result)
    validate_result(result)
    write_result(output, result)
    return {"case_id": case_id, "frames": expected_frames,
            "pipeline_manifest_sha256": _hash(capture_root / "manifest.json"),
            "result_sha256": _hash(output / "result.json")}


def seal_reviewed(output: Path, restoration: dict) -> dict:
    """Seal only after the operator session actually reports world restoration."""
    from worker_exchange.native_output import seal_capture
    if not isinstance(restoration, dict) or restoration.get("restored") is not True or not restoration.get("source"):
        raise ValueError("Original operator restoration receipt required")
    output = Path(output).resolve()
    result = json.loads((output / "result.json").read_text())
    frames = len(_rows(output / result["video_frame_map_reference"]))
    return seal_capture(output, frames=frames, restoration=restoration,
                        errors=[], encoder_exit_codes={name: 0 for name in VIEWS})
