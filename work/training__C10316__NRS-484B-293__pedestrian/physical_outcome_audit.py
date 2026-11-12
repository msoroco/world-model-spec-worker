"""Independent source-frame motion check for the selected crosswalk pair.

The right-half measurement is descriptive. Practicability and legal judgment
require separate original-source review. Synthetic inputs never prove Native
motion, even when their source-shaped path satisfies the measurement algorithm.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path


HERE = Path(__file__).resolve().parent
SOURCES = ("native_samples.jsonl", "trace.jsonl", "capture/evidence.jsonl",
           "video_frames.jsonl", "capture/native/frames.jsonl",
           "crosswalk-context.json", "capture/manifest.json")


def require(ok: bool, message: str) -> None:
    if not ok:
        raise ValueError(message)


def read(path: Path) -> dict:
    return json.loads(path.read_text())


def rows(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines()
            if line.strip()]


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def classify(samples: list[dict], mapping: list[dict], context: dict,
             expected_half: str) -> dict:
    require(expected_half in {"right", "left"}, "Unknown exact crosswalk half")
    require(len(samples) == len(mapping) == 240,
            "Full 240-frame crosswalk interval required")
    cx, cy = context["crosswalk_center_xy_m"]
    fx, fy = context["crosswalk_passage_forward_xy"]
    require(abs(math.hypot(fx, fy) - 1) <= 1e-6 and
            context["crosswalk_length_m"] > 0 and
            context["crosswalk_width_m"] > 0,
            "Crosswalk geometry or passage direction invalid")
    rx, ry = fy, -fx
    half_length = context["crosswalk_length_m"] / 2
    half_width = context["crosswalk_width_m"] / 2
    counts = {"right": 0, "left": 0, "center_or_straddling": 0}
    frames = []
    longitudinal_centers = []
    previous_frame, previous_time = -1, -math.inf
    for index, (sample, frame) in enumerate(zip(samples, mapping)):
        require(sample["native_frame"] == frame["native_frame"] and
                frame["native_frame"] > previous_frame and
                frame["time_s"] > previous_time and
                frame["video_frame"] == index and
                abs(sample["time_s"] - frame["time_s"]) <= 1e-4 and
                sample["crosswalk_id"] == context["crosswalk_id"],
                "Source frame/time or crosswalk identity differs")
        corners = sample["pedestrian_footprint_xy_m"]
        require(isinstance(corners, list) and len(corners) == 4 and
                all(isinstance(v, list) and len(v) == 2 and
                    all(type(x) in (int, float) and math.isfinite(x) for x in v)
                    for v in corners),
                "Original pedestrian footprint missing")
        center_x, center_y = sample["pedestrian_xy_m"]
        longitudinal_centers.append((center_x-cx)*fx+(center_y-cy)*fy)
        projected = [((x-cx)*fx+(y-cy)*fy, (x-cx)*rx+(y-cy)*ry)
                     for x, y in corners]
        if all(abs(u) <= half_length + 1e-6 and
               abs(v) <= half_width + 1e-6 for u, v in projected):
            lateral = [v for _, v in projected]
            category = ("right" if all(v > .01 for v in lateral) else
                        "left" if all(v < -.01 for v in lateral) else
                        "center_or_straddling")
            counts[category] += 1
            frames.append(frame["native_frame"])
        previous_frame, previous_time = frame["native_frame"], frame["time_s"]
    traversed = (longitudinal_centers[0] < -half_length and
                 longitudinal_centers[-1] > half_length and
                 all(b >= a - 1e-4 for a, b in
                     zip(longitudinal_centers, longitudinal_centers[1:])))
    if not traversed:
        status, reason = "not_met", "full forward crosswalk traversal absent"
    elif not frames:
        status, reason = "not_met", "no full-footprint crosswalk passage"
    elif len(frames) < 60:
        status, reason = "not_met", "crosswalk passage shorter than observed fixture target"
    elif counts[expected_half] == len(frames):
        status, reason = "met", "all contained source frames in requested half"
    else:
        status, reason = "not_met", "passage includes another half or center"
    return {"status": status, "reason": reason, "expected_half": expected_half,
            "full_forward_traversal": traversed,
            "crosswalk_frames": len(frames), "half_counts": counts,
            "first_frame": frames[0] if frames else None,
            "last_frame": frames[-1] if frames else None}


def audit(attempt: Path, case_id: str, *, test_shape: bool = False) -> dict:
    attempt = attempt.resolve()
    require(case_id in {HERE.name + "__reference", HERE.name + "__contrast"},
            "Physical outcome selects another case")
    existing = {name: sha(attempt / name) for name in SOURCES
                if (attempt / name).is_file()}
    missing = sorted(set(SOURCES) - set(existing))
    if missing:
        return {"format": "c10316-independent-motion-outcome-v1",
                "case_id": case_id, "source_shaped_unit_test": test_shape,
                "motion_status": "unverified", "native_motion_status": "unverified",
                "missing_sources": missing, "source_sha256": existing,
                "physical_acceptance_claimed": False,
                "legal_verdict_claimed": False}
    context = read(attempt / "crosswalk-context.json")
    capture = read(attempt / "capture/manifest.json")
    require((context.get("source_kind") == "synthetic_scene_request" and
             capture.get("synthetic_diagnostic") is True) if test_shape else
            (context.get("source_kind") == "native_observation" and
             capture.get("synthetic_diagnostic") is not True and
             (attempt / "capture-seal.json").is_file()),
            "Synthetic or unsealed source cannot prove original Native motion")
    if not test_shape:
        seal_path = attempt / "capture-seal.json"
        exit_path = attempt / "native-exit.json"
        require(exit_path.is_file(), "Original Native exit record missing")
        seal, exit_record = read(seal_path), read(exit_path)
        require(seal.get("format") == "worker-sealed-capture" and
                seal.get("provenance_kind") == "native" and
                seal.get("diagnostic_fixture") is False and
                seal.get("frames") == 240 and
                exit_record.get("event") == "native_exit" and
                exit_record.get("capture_failed") is not True and
                exit_record.get("native_process_exit_code") == 0 and
                exit_record.get("capture_seal_sha256") == sha(seal_path),
                "Original Native capture closure differs")
        sealed = seal.get("sources", {})
        require(set(SOURCES) <= set(sealed) and
                all(name in sealed for name in
                    ("overview.mkv", "approach.mkv", "reference_corner.mkv",
                     "driver_reference.mkv")),
                "Original Native source inventory incomplete")
        for name, digest in sealed.items():
            source_path = (attempt / name).resolve()
            require(attempt in source_path.parents and source_path.is_file() and
                    sha(source_path) == digest,
                    "Sealed original source changed: " + name)
    source = {name: rows(attempt / name) for name in SOURCES[:5]}
    samples, trace, evidence, mapping, native = (source[name] for name in SOURCES[:5])
    require(all(len(item) == 240 for item in source.values()) and
            capture.get("frames") == 240 and
            capture.get("extraction_confirmed") is True,
            "Original crosswalk source interval incomplete")
    for sample, t, e, m, n in zip(samples, trace, evidence, mapping, native):
        require(sample["native_frame"] == t["frame"] == e["original_frame"] ==
                m["native_frame"] == m["carla_frame"] == n["frame"] and
                abs(sample["time_s"] - t["time_s"]) <= 1e-4 and
                abs(sample["time_s"] - e["recording_time_s"]) <= 1e-4 and
                abs(sample["time_s"] - m["time_s"]) <= 1e-4 and
                sample["pedestrian_xy_m"] == e["ego"]["position_m"][:2] and
                {(round(x, 3), round(y, 3)) for x, y in
                 sample["pedestrian_footprint_xy_m"]} ==
                {(round(v[0], 3), round(v[1], 3)) for v in
                 e["ego"]["body_vertices_m"]},
                "Original pedestrian pose, footprint or frame join differs")
        require(e["ego"].get("speed_provenance") == "synthetic_native_sample"
                if test_shape else
                e["ego"].get("speed_provenance") != "synthetic_native_sample",
                "Synthetic speed cannot prove original Native motion")
    expected = "right" if case_id.endswith("__reference") else "left"
    motion = classify(samples, mapping, context, expected)
    return {"format": "c10316-independent-motion-outcome-v1",
            "case_id": case_id, "source_shaped_unit_test": test_shape,
            "motion_status": motion["status"] if not test_shape else "unverified",
            "source_shaped_motion_status": motion["status"] if test_shape else None,
            "native_motion_status": motion["status"] if not test_shape else "unverified",
            "measured": motion, "missing_sources": [],
            "source_sha256": existing,
            "practicability_verified": False,
            "physical_acceptance_claimed": False,
            "legal_verdict_claimed": False}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", type=Path, required=True)
    parser.add_argument("--case", required=True)
    args = parser.parse_args()
    print(json.dumps(audit(args.attempt, args.case), indent=2))
