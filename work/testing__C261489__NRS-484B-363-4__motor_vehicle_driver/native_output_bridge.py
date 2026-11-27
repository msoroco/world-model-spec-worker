"""Seal original school-pass packets into the runtime's saved processing shape."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess

from native_capture import FRAMES, RATE, VIEWS
from school_pass import ASSIGNMENT


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(ok: bool, message: str) -> None:
    if not ok:
        raise ValueError(message)


def write_json(path: Path, value: dict) -> None:
    with path.open("x") as stream:
        json.dump(value, stream, sort_keys=True, separators=(",", ":"), allow_nan=False)
        stream.write("\n")


def compose(root: Path) -> None:
    inputs = []
    for view in VIEWS:
        inputs.extend(["-i", str(root / (view + ".mkv"))])
    filter_graph = "[0:v]scale=1920:1080[a];[1:v]scale=1920:1080[b];[2:v]scale=1920:1080[c];[3:v]scale=1920:1080[d];[a][b][c][d]xstack=inputs=4:layout=0_0|1920_0|0_1080|1920_1080[v]"
    command = ["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-y",
               *inputs, "-filter_complex", filter_graph, "-map", "[v]", "-an",
               "-r", str(RATE), "-frames:v", str(FRAMES), "-c:v", "libx264",
               "-preset", "fast", "-crf", "18", str(root / "raw.mkv")]
    result = subprocess.run(command, capture_output=True, text=True, timeout=1800)
    if result.returncode:
        raise ValueError("four-view original composition failed: " + result.stderr[-1000:])


def publish(root: Path, *, map_bytes: bytes, restored: bool) -> dict:
    root = Path(root)
    require(restored is True and type(map_bytes) is bytes and bool(map_bytes),
            "Native world restoration and map bytes required")
    config = json.loads((root / "config.json").read_text())
    construction = json.loads((root / "construction.json").read_text())
    receipt_path = root / "receipt.json"
    receipt = json.loads(receipt_path.read_text())
    case_id = receipt.get("case_id")
    require(case_id.startswith(ASSIGNMENT + "__") and config.get("selected_case_id") == case_id and
            construction.get("case_id") == case_id and receipt.get("source_kind") == "original_native_capture",
            "original school pass case or source identity differs")
    paths = {key: root / name for key, name in (
        ("context_sha256", "context.json"), ("trace_sha256", "original-trace.jsonl"),
        ("camera_manifest_sha256", "cameras.json"))}
    for key, path in paths.items():
        require(receipt.get(key) == sha(path), "sealed original source changed: " + path.name)
    context = json.loads((root / "context.json").read_text())
    original = [json.loads(line) for line in (root / "original-trace.jsonl").read_text().splitlines()]
    cameras = json.loads((root / "cameras.json").read_text())
    require(len(original) == FRAMES and receipt.get("frame_count") == FRAMES and
            cameras.get("frame_count") == FRAMES and receipt.get("fps") == RATE and
            cameras.get("fps") == RATE,
            "original Native frame count/cadence incomplete")
    require(set(cameras.get("streams", {})) == set(VIEWS), "four original cameras missing")
    for view in VIEWS:
        item = cameras["streams"][view]
        require(item.get("path") == view + ".mkv" and item.get("sha256") == sha(root / item["path"]),
                "original camera stream source changed: " + view)
    require(context.get("site_sha256") == receipt.get("site_sha256") and
            context.get("map_sha256") == hashlib.sha256(map_bytes).hexdigest() and
            sha(root / "road.xodr") == hashlib.sha256(map_bytes).hexdigest(),
            "reviewed original map or site source differs")
    pipeline = json.loads((root / "capture/manifest.json").read_text())
    require(pipeline.get("extraction_confirmed") is True and pipeline.get("frames") == FRAMES,
            "pinned original PipelineCapture incomplete")
    trace = [json.loads(line) for line in (root / "trace.jsonl").read_text().splitlines()]
    require(len(trace) == FRAMES and
            all(trace[i]["frame"] == original[i]["original_frame"] and
                abs(trace[i]["time_s"] - original[i]["time_s"]) <= .002
                for i in range(FRAMES)),
            "pinned Core trace differs from original school pass frames")
    compose(root)
    frame_map_path = root / "video_frames.jsonl"
    with frame_map_path.open("x") as stream:
        for index, row in enumerate(original):
            stream.write(json.dumps({"video_frame": index, "carla_frame": row["original_frame"],
                                     "time_s": row["time_s"]}, sort_keys=True) + "\n")
    evidence = []
    channels = root / "channels"
    channels.mkdir(exist_ok=False)
    source_hashes = {"context.json": sha(root / "context.json"),
                     "original-trace.jsonl": sha(root / "original-trace.jsonl"),
                     "cameras.json": sha(root / "cameras.json")}
    for channel in construction["recording_description"]["channels"]:
        name = channel["name"]
        relative = "channels/" + name + ".jsonl"
        with (root / relative).open("x") as stream:
            for row in original:
                stream.write(json.dumps({"time_s": row["time_s"],
                                         "value": {"case_id": case_id, "source_hashes": source_hashes,
                                                   "original_frame": row["original_frame"]}}, sort_keys=True) + "\n")
        evidence.append({"name": name, "unit": channel["unit"], "reference": relative})
    context_relative = "channels/reviewed_original_school_sources.json"
    write_json(root / context_relative, {"reviewed_original_school_sources": {
        "site_sha256": receipt["site_sha256"], "source_hashes": source_hashes,
        "legal_judgment": "unresolved"}})
    evidence.append({"name": "reviewed_original_school_sources", "unit": "source",
                     "reference": context_relative})
    measured = receipt["measurement"]
    result = {
        "case_id": case_id, "measured_values": measured,
        "target_checks": [{"target": "source-bound same-direction school-zone pass",
                           "requested": config["case"]["case_id"], "measured": measured,
                           "method": "school_pass.measure_original", "tolerance": 0,
                           "matched": True, "physical_cause_confirmed": False,
                           "cause_evidence": source_hashes}],
        "setup_confirmed": False, "behavior_attempted": bool(context["pass_requested"]),
        "maneuver_completed": bool(measured["completed_pass"]),
        "termination_reason": "Original school-zone source and camera review pending",
        "physical_failure_flags": [], "trace_reference": "trace.jsonl",
        "video_references": [view + ".mkv" for view in VIEWS] + ["raw.mkv"],
        "video_frame_map_reference": "video_frames.jsonl",
        "recording_description": construction["recording_description"],
        "recording_evidence": evidence, "realized_observables": {},
        "legal_judgment": None, "physical_acceptance_claimed": False,
    }
    write_json(root / "result.json", result)
    return result
