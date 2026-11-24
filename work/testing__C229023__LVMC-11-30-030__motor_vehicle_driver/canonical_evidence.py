"""Project a sealed Native crosswalk capture into canonical recording evidence.

This writes derived files into a saved attempt. Original acquisition is read only.
"""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

from build_semantic_draft import recording_description
from crosswalk_measurements import ASSIGNMENT_ID


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _rows(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line]


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    with path.open("x", encoding="utf-8") as stream:
        for row in rows:
            stream.write(json.dumps(row, sort_keys=True, allow_nan=False) + "\n")


def project(attempt: str | Path, case_id: str, media: dict | None = None) -> tuple[dict, list[dict], dict]:
    """Return the frozen channel plan, references and source-bound derived files."""
    root = Path(attempt).resolve()
    source_names = ("context.json", "trace.jsonl", "frame-map.jsonl", "receipt.json")
    sources = {name: root / name for name in source_names}
    if any(not path.is_file() or path.is_symlink() for path in sources.values()):
        raise ValueError("complete original crosswalk source set required")
    before = {name: _sha(path) for name, path in sources.items()}
    context = json.loads(sources["context.json"].read_text())
    receipt = json.loads(sources["receipt.json"].read_text())
    trace = _rows(sources["trace.jsonl"])
    mapping = _rows(sources["frame-map.jsonl"])
    if (case_id != context.get("case_id") or case_id != receipt.get("case_id") or
            receipt.get("assignment_id") != ASSIGNMENT_ID or receipt.get("diagnostic_fixture") or
            len(trace) != len(mapping) or len(trace) != 900 or receipt.get("frame_count") != 900 or
            receipt.get("fps") != 20 or before["context.json"] != receipt.get("context_sha256") or
            before["trace.jsonl"] != receipt.get("trace_sha256") or
            before["frame-map.jsonl"] != receipt.get("frame_map_sha256")):
        raise ValueError("exact sealed 900-frame Native crosswalk source required")
    for index, (row, frame) in enumerate(zip(trace, mapping)):
        if (frame.get("video_frame") != index or frame.get("carla_frame") != row.get("frame") or
                frame.get("time_s") != row.get("time_s") or
                abs(row["time_s"] - index / 20) > 1e-5):
            raise ValueError("original actor/frame-map identity or cadence differs")
        for role in ("ego", "lead"):
            center = row.get(role + "_center")
            vertices = row.get(role + "_vertices")
            if (not isinstance(center, list) or len(center) != 2 or
                    not isinstance(vertices, list) or len(vertices) != 8 or
                    not all(isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)
                            for v in center)):
                raise ValueError("original actor geometry missing")
        if not isinstance(row.get("pedestrian_center"), list) or len(row["pedestrian_center"]) != 2:
            raise ValueError("original pedestrian center missing")
    video_binding = None
    if media is not None:
        videos = media.get("videos")
        if (media.get("case_id") != case_id or
                media.get("frame_map_sha256") != before["frame-map.jsonl"] or
                not isinstance(videos, dict) or
                set(videos) != {"overview", "approach", "reference_corner", "driver_reference"}):
            raise ValueError("saved four-view decoded media differs from original capture")
        video_binding = {}
        for name, decoded in videos.items():
            path = root / (name + ".mkv")
            if (not path.is_file() or path.is_symlink() or decoded.get("frames") != 900 or
                    decoded.get("video_sha256") != _sha(path) or
                    not isinstance(decoded.get("rgb_sha256"), str) or
                    len(decoded["rgb_sha256"]) != 64):
                raise ValueError("saved decoded camera source differs: " + name)
            video_binding[name] = {"video_sha256": decoded["video_sha256"],
                                   "decoded_rgb_sha256": decoded["rgb_sha256"]}
    planned = recording_description()
    channel_values = {
        "ego_body_history": [{"center": r["ego_center"], "vertices": r["ego_vertices"],
                              "speed_mps": r["ego_speed_mps"]} for r in trace],
        "lead_body_history": [{"center": r["lead_center"], "vertices": r["lead_vertices"],
                               "speed_mps": r["lead_speed_mps"]} for r in trace],
        "original_actor_body_sequence": [{"ego": r["ego_center"], "lead": r["lead_center"],
                                          "pedestrian": r["pedestrian_center"],
                                          "sources": r["actor_sources"]} for r in trace],
        "pedestrian_history": [{"center": r["pedestrian_center"],
                                "source": r["actor_sources"]["pedestrian"]} for r in trace],
        "four_camera_frame_map": mapping,
        "complete_native_source_and_pixels": [
            {"actor_source": r["actor_sources"], "camera_frame": m["video_frame"],
             "carla_frame": m["carla_frame"], "decoded_media": video_binding}
            for r, m in zip(trace, mapping)],
    }
    if {c["name"] for c in planned["channels"]} != set(channel_values):
        raise ValueError("canonical channel plan differs from source projection")
    derived = root / "canonical-evidence"
    derived.mkdir(exist_ok=False)
    evidence = []
    for channel in planned["channels"]:
        name = channel["name"]
        path = derived / (name + ".jsonl")
        _write_jsonl(path, [{"time_s": row["time_s"], "value": value}
                            for row, value in zip(trace, channel_values[name])])
        evidence.append({"name": name, "unit": channel["unit"],
                         "reference": str(path.relative_to(root))})
    source_context = {
        "intersection_crosswalk_geometry": {
            "map_sha256": context["map_sha256"], "junction_kind": context["junction_kind"],
            "crosswalk": context["crosswalk"], "road_axis": context["road_axis"]},
        "lead_stop_purpose": context["stopped_vehicle_purpose"],
        "original_crosswalk_and_purpose": {
            "crosswalk": context["crosswalk"],
            "purpose": context["stopped_vehicle_purpose"],
            "source_sha256": before},
    }
    context_path = derived / "context.json"
    context_path.write_text(json.dumps(source_context, sort_keys=True, allow_nan=False) + "\n")
    for item in planned["context_inputs"]:
        if item["name"] not in source_context:
            raise ValueError("canonical context input missing")
        evidence.append({"name": item["name"], "unit": item["unit"],
                         "reference": str(context_path.relative_to(root))})
    if any(_sha(path) != before[name] for name, path in sources.items()):
        raise ValueError("canonical projection changed original acquisition")
    return planned, evidence, before


def build_result(attempt: str | Path, case_id: str, finalized: dict) -> dict:
    """Build a native result from original sources and saved measurements.

    Source presence and sampled target matching are reported separately from
    physical causation and any legal judgment, which remain unverified.
    """
    root = Path(attempt).resolve()
    if finalized.get("case_id") != case_id:
        raise ValueError("saved crosswalk measurement case differs")
    media = finalized.get("media")
    if not isinstance(media, dict):
        raise ValueError("saved four-view decode audit required")
    planned, evidence, hashes = project(root, case_id, media)
    context = json.loads((root / "context.json").read_text())
    trace = _rows(root / "trace.jsonl")
    axis = context["road_axis"]["forward"]
    heading = math.degrees(math.atan2(axis[1], axis[0]))
    native_trace = root / "canonical-evidence/native-trace.jsonl"
    _write_jsonl(native_trace, [
        {"frame": row["frame"], "time_s": row["time_s"],
         "position": {"x": row["ego_center"][0], "y": row["ego_center"][1],
                      "z": sum(vertex[2] for vertex in row["ego_vertices"]) / 8},
         "heading_deg": heading, "speed_mps": row["ego_speed_mps"]}
        for row in trace])
    checked = []
    for item in finalized["target_checks"]:
        if not isinstance(item.get("measured"), bool) or not isinstance(item.get("requested"), bool):
            raise ValueError("saved observation target must be explicit boolean")
        checked.append({"target": item["target"], "requested": item["requested"],
                        "measured": item["measured"],
                        "method": "sealed original 20 Hz actor geometry and speed samples",
                        "tolerance": 0, "matched": item["matched"],
                        "physical_cause_confirmed": False,
                        "cause_evidence": {"status": "independent physical review pending"}})
    if len(checked) != 4:
        raise ValueError("four exact crosswalk observation targets required")
    videos = [name + ".mkv" for name in
              ("overview", "approach", "reference_corner", "driver_reference")]
    if any(not (root / name).is_file() for name in videos):
        raise ValueError("four saved Native camera sources required")
    if any(_sha(root / name) != digest for name, digest in hashes.items()):
        raise ValueError("native result projection changed original acquisition")
    return {"case_id": case_id, "measured_values": finalized["measured_values"],
            "target_checks": checked, "setup_confirmed": False,
            "behavior_attempted": False, "maneuver_completed": False,
            "termination_reason": "Original capture measured; independent physical review pending",
            "physical_failure_flags": {"physical_review_pending": True},
            "trace_reference": str(native_trace.relative_to(root)),
            "video_references": videos, "video_frame_map_reference": "frame-map.jsonl",
            "recording_description": planned, "recording_evidence": evidence,
            "realized_observables": {},
            "source_sha256": {**hashes, **{name + ".mkv": item["video_sha256"]
                                          for name, item in media["videos"].items()}},
            "physical_acceptance": "unverified", "legal_judgment": "unresolved"}
