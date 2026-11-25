"""Selected saved-only measurements for the C158208 nearest-view cases.

This entrypoint reads sealed original ticks and camera archives. Its report is
an engineering observation; no controller label is treated as a legal verdict.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import subprocess

from camera_sources import CAMERAS, audit_camera_sources
from nearest_view_measurement import measure
from native_attempt import verify_review_sources
from prepare_derived_media import prepare as prepare_derived_media
from source_tick_capture import verify_seal


ASSIGNMENT = "testing__C158208__NRS-484B-257-1__motor_vehicle_driver"
REQUIRED = ("capture-identity.json", "nearest-view-tick-seal.json",
            "nearest-view-original-ticks.jsonl", "nearest-view-saved-packet.json")


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _sources(root: Path) -> dict:
    marker = root / "diagnostic-compatibility.json"
    names = REQUIRED + ((marker.name,) if marker.is_file() else
                        ("nearest-view-camera-manifest.json",))
    for name in names:
        if not (root / name).is_file():
            raise ValueError("Missing required source: " + name)
    return {name: _sha(root / name) for name in names}


def _diagnostic_videos(root: Path, case_id: str, expected_frames: int) -> dict:
    marker = json.loads((root / "diagnostic-compatibility.json").read_text())
    if marker != {"format": "c158208-generated-compatibility-v1", "case_id": case_id,
                   "frame_count": expected_frames, "source_kind": "synthetic_fixture"}:
        raise ValueError("diagnostic compatibility source identity differs")
    dimensions = {"overview": (1920, 1080), "approach": (1280, 720),
                  "reference_corner": (1280, 720), "driver_reference": (1280, 720)}
    videos = {}
    for name in CAMERAS:
        path = root / (name + ".mkv")
        if not path.is_file():
            raise ValueError("Missing required source: " + path.name)
        probe = subprocess.run(["ffprobe", "-v", "error", "-count_frames",
                                "-select_streams", "v:0", "-show_entries",
                                "stream=width,height,nb_read_frames,r_frame_rate", "-of", "json",
                                str(path)], capture_output=True, text=True, check=True)
        stream = json.loads(probe.stdout)["streams"][0]
        if ((stream["width"], stream["height"]) != dimensions[name] or
                stream["r_frame_rate"] != "20/1" or
                int(stream["nb_read_frames"]) != expected_frames):
            raise ValueError("diagnostic camera shape or frames differ: " + name)
        videos[name] = {"path": path.name, "sha256": _sha(path)}
    return {"format": "c158208-generated-compatibility-v1", "frame_count": expected_frames,
            "videos": videos, "diagnostic_fixture": True}


def measure_nearest_view(stage: Path) -> dict:
    root = Path(stage)
    hashes = _sources(root)
    packet = verify_seal(root)
    identity = json.loads((root / "capture-identity.json").read_text())
    if identity.get("assignment_id") != ASSIGNMENT or identity.get("case_id") not in {
            ASSIGNMENT + "__nearest_view_response",
            ASSIGNMENT + "__nearest_view_uninterrupted"}:
        raise ValueError("selected C158208 capture identity differs")
    diagnostic = identity.get("provenance_kind") == "synthetic_fixture"
    config_path = root / "config.json"
    if config_path.is_file():
        config = json.loads(config_path.read_text())
        if config.get("selected_case_id") != identity["case_id"]:
            raise ValueError("selected Native case differs from sealed capture")
    construction_path = root / "construction.json"
    if construction_path.is_file() and not diagnostic and \
            _sha(construction_path) != identity.get("construction_sha256"):
        raise ValueError("selected construction differs from sealed original capture")
    if not diagnostic and identity.get("provenance_kind") != "original_capture":
        raise ValueError("unknown source provenance")
    if not diagnostic:
        scene_path = root / "scene.json"
        if not scene_path.is_file():
            raise ValueError("Missing required source: scene.json")
        scene = json.loads(scene_path.read_text())
        if scene.get("source_kind") != "original_reviewed_site":
            raise ValueError("original capture requires reviewed scene")
        site_name = scene.get("site_source")
        if not isinstance(site_name, str) or Path(site_name).name != site_name:
            raise ValueError("reviewed site source path differs")
        site_path = root / site_name
        if not site_path.is_file():
            raise ValueError("Missing required source: " + site_name)
        if _sha(site_path) != scene.get("site_sha256") or _sha(site_path) != identity.get("site_packet_sha256"):
            raise ValueError("reviewed site differs from sealed original capture")
        site = json.loads(site_path.read_text())
        verify_review_sources(site, site_path, diagnostic_fixture=False)
        if site.get("capture_geometry") != packet["geometry"] or site.get("reviewed_context") != packet["reviewed_context"]:
            raise ValueError("reviewed site geometry or context differs from sealed original ticks")
    value = measure(packet)
    generated = diagnostic and (root / "diagnostic-compatibility.json").is_file()
    cameras = (_diagnostic_videos(root, identity["case_id"], value["sample_count"])
               if generated else audit_camera_sources(root, diagnostic_fixture=diagnostic))
    if value["sample_count"] != cameras["frame_count"]:
        raise ValueError("original tick and camera frame counts differ")
    if generated:
        hashes.update({source["path"]: source["sha256"] for source in cameras["videos"].values()})
    else:
        for name, source in json.loads((root / "nearest-view-camera-manifest.json").read_text())["sources"].items():
            path = root / source["path"]
            if not path.is_file():
                raise ValueError("Missing required source: " + source["path"])
            hashes[source["path"]] = _sha(path)
    return {"method": "measure_nearest_view", "value": value,
            "sources": hashes, "diagnostic_fixture": diagnostic,
            "case_id": identity["case_id"]}


def measure_governing_control(stage: Path) -> dict:
    root = Path(stage)
    joined = measure_nearest_view(root)
    packet = verify_seal(root)
    context = packet["reviewed_context"]
    observed = {name: context[name] for name in (
        "yield_sign_governs_approach", "no_marked_stop_line",
        "no_near_side_crosswalk", "no_sidewalk_derived_crosswalk",
        "through_highway_confirmed", "no_officer_control", "no_signal_control",
        "viewpoint_reviewed")}
    return {"method": "measure_governing_control", "value": observed,
            "sources": joined["sources"], "diagnostic_fixture": joined["diagnostic_fixture"],
            "case_id": joined["case_id"]}


def _native_result(root: Path, nearest: dict, control: dict) -> dict:
    config = json.loads((root / "config.json").read_text())
    construction = json.loads((root / "construction.json").read_text())
    description = construction["recording_description"]
    if construction["case_id"] != nearest["case_id"] or config["selected_case_id"] != nearest["case_id"]:
        raise ValueError("selected construction differs from sealed capture")
    packet = verify_seal(root)
    samples = packet["samples"]
    originals = [json.loads(line) for line in
                 (root / "nearest-view-original-ticks.jsonl").read_text().splitlines()]
    if len(originals) != len(samples):
        raise ValueError("original tick and saved sample counts differ")
    if len(samples) != config["rate_hz"] * config["duration_s"] and not nearest["diagnostic_fixture"]:
        raise ValueError("incomplete original production frame count")
    generated = nearest["diagnostic_fixture"] and (root / "diagnostic-compatibility.json").is_file()
    media = (_diagnostic_videos(root, nearest["case_id"], len(samples)) if generated else
             prepare_derived_media(root, diagnostic_fixture=nearest["diagnostic_fixture"],
                                   reuse_existing=True))
    camera = (None if generated else
              json.loads((root / "nearest-view-camera-manifest.json").read_text()))
    channel_root = root / "channels"
    channel_root.mkdir(exist_ok=False)
    traces = []
    mappings = []
    projections = {
        "ego_body_and_speed": lambda row, raw, index: {
            "body_vertices_xy_m": raw["ego"]["body_vertices_xy_m"],
            "speed_mps": row["ego_speed_mps"]},
        "through_vehicle_body_and_occupancy": lambda row, raw, index: {
            "body_vertices_xy_m": raw["through_vehicle"]["body_vertices_xy_m"],
            "within_intersection": row["through_vehicle_within_intersection"]},
        "nearest_view_raycast": lambda row, raw, index: {
            "probe": raw["visibility_probe"], "visible": row["through_traffic_visible"]},
        "camera_pixels": lambda row, raw, index: (
            {name: item["sha256"] for name, item in media["videos"].items()} if generated
            else camera["rows"][index]["cameras"]),
    }
    evidence = []
    for channel in description["channels"]:
        name = channel["name"]
        if name not in projections:
            raise ValueError("selected channel has no original projection: " + name)
        target = channel_root / (name + ".jsonl")
        with target.open("x") as stream:
            for index, (row, raw) in enumerate(zip(samples, originals)):
                stream.write(json.dumps({"time_s": row["time_s"],
                                         "value": projections[name](row, raw, index)}) + "\n")
        evidence.append({"name": name, "unit": channel["unit"],
                         "reference": str(target.relative_to(root))})
    contexts = {"reviewed_site": packet["reviewed_context"],
                "governing_control": control["value"]}
    for item in description["context_inputs"]:
        name = item["name"]
        if name not in contexts:
            raise ValueError("selected context has no original projection: " + name)
        target = channel_root / (name + ".json")
        target.write_text(json.dumps({name: contexts[name]}) + "\n")
        evidence.append({"name": name, "unit": item["unit"],
                         "reference": str(target.relative_to(root))})
    for index, (row, raw) in enumerate(zip(samples, originals)):
        vertices = raw["ego"]["body_vertices_xy_m"]
        velocity = raw["ego"]["velocity_xy_mps"]
        center = [sum(p[axis] for p in vertices) / len(vertices) for axis in (0, 1)]
        traces.append({"frame": row["frame"], "time_s": row["time_s"],
                       "position_m": [center[0], center[1], 0.0],
                       "position": {"x": center[0], "y": center[1], "z": 0.0},
                       "heading_deg": math.degrees(math.atan2(velocity[1], velocity[0])),
                       "speed_mps": row["ego_speed_mps"],
                       "speed_mph": row["ego_speed_mps"] / .44704,
                       "velocity_mps": [velocity[0], velocity[1], 0.0],
                       "control": {}})
        mappings.append({"video_frame": index, "carla_frame": row["frame"],
                         "native_frame": row["frame"],
                         "time_s": row["time_s"]})
    for name, rows in (("trace.jsonl", traces), ("video_frames.jsonl", mappings)):
        target = root / name
        content = "".join(json.dumps(row) + "\n" for row in rows)
        if target.exists():
            if target.read_text() != content:
                raise ValueError("sealed original frame stream differs: " + name)
        else:
            target.write_text(content)
    check = {"target": "sealed original nearest-view source join", "requested": True,
             "measured": True, "method": "measure_nearest_view", "tolerance": 0,
             "matched": True, "physical_cause_confirmed": False,
             "cause_evidence": nearest["sources"]}
    result = {"case_id": nearest["case_id"], "measured_values": nearest["value"],
              "target_checks": [check], "setup_confirmed": False,
              "behavior_attempted": False, "maneuver_completed": False,
              "termination_reason": "Saved original source measurements; physical review pending",
              "physical_failure_flags": [], "trace_reference": "trace.jsonl",
              "video_references": [name + ".mkv" for name in CAMERAS],
              "video_frame_map_reference": "video_frames.jsonl",
              "recording_description": description, "recording_evidence": evidence,
              "realized_observables": {}, "legal_judgment": None,
              "diagnostic_fixture": nearest["diagnostic_fixture"],
              "source_media": media}
    (root / "result.json").write_text(json.dumps(result, indent=2) + "\n")
    return result


def analyze(stage: Path, output: Path) -> dict:
    root = Path(stage)
    nearest = measure_nearest_view(root)
    control = measure_governing_control(root)
    report = {"format": "worker-analysis-report", "case_id": nearest["case_id"],
              "measurements": {"nearest_view_history": nearest,
                               "governing_control_context": control},
              "diagnostic_fixture": nearest["diagnostic_fixture"],
              "legal_judgment": None,
              "limitations": ["Original source measurements do not determine immediate hazard or right of way."]}
    if (root / "config.json").is_file() and (root / "construction.json").is_file():
        _native_result(root, nearest, control)
    output = Path(output)
    if output.exists():
        raise ValueError("analysis report already exists")
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    print(analyze(args.attempt, args.output)["case_id"])
