"""Independent C104538 reversal check from retained motion sources.

The diagnostic mode tests geometry and joins. Only a sealed original Native
capture can report a completed physical maneuver; visibility is separate.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

SOURCES = ("config.json", "native_body_history.jsonl", "trace.jsonl",
           "capture/evidence.jsonl", "video_frames.jsonl",
           "acquisition-provenance.json")
CAMERAS = ("overview.mkv", "approach.mkv", "reference_corner.mkv",
           "driver_reference.mkv")
LIFECYCLE = ("capture_finished", "encoders_closed", "restoration_verified",
             "native_exit", "owner_released", "saved_processing_started")


def require(ok: bool, message: str) -> None:
    if not ok:
        raise ValueError(message)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path: Path) -> dict:
    return json.loads(path.read_text())


def rows(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def finite(value: object) -> bool:
    return type(value) in (int, float) and math.isfinite(value)


def check_lifecycle(events: list[str]) -> dict:
    require(events == list(LIFECYCLE), "Saved processing preceded Native ownership closure")
    return {"events": events, "saved_processing_after_owner_release": True}


def classify(history: list[dict], trace: list[dict], evidence: list[dict],
             mapping: list[dict], expected: int) -> dict:
    require(len(history) == len(trace) == len(evidence) == len(mapping) == expected,
            "Complete original motion interval required")
    centers, headings, signed_velocity = [], [], []
    previous_frame, previous_time = -1, -math.inf
    for index, (body, movement, capture, frame) in enumerate(
            zip(history, trace, evidence, mapping)):
        ident, time = frame["native_frame"], frame["time_s"]
        require(type(ident) is int and ident > previous_frame and
                finite(time) and time > previous_time and
                frame["carla_frame"] == ident and frame["video_frame"] == index and
                body["native_frame"] == movement["frame"] ==
                capture["original_frame"] == ident and
                all(finite(t) and abs(t-time) <= 1e-4 for t in
                    (body["time_s"], movement["time_s"],
                     capture["recording_time_s"])),
                "Original motion/frame/time join differs")
        vertices = body["ego_body_vertices_m"]
        require(len(vertices) >= 4 and all(len(v) >= 3 and
                all(finite(x) for x in v[:3]) for v in vertices) and
                vertices == capture["ego"]["body_vertices_m"] ==
                movement["c104538_native"]["ego_body_vertices_m"],
                "Original body geometry differs")
        center = [sum(v[i] for v in vertices)/len(vertices) for i in range(3)]
        require(all(abs(a-b) <= 1e-4 for a, b in
                    zip(center, body["ego_center_xyz_m"])) and
                body["ego_center_xyz_m"] == movement["position_m"],
                "Original body center differs")
        heading = body["ego_heading_deg"]
        velocity = movement["velocity_mps"]
        require(finite(heading) and heading == capture["ego"]["heading_deg"] and
                len(velocity) >= 2 and all(finite(v) for v in velocity[:2]),
                "Original heading or velocity missing")
        centers.append(center)
        headings.append(heading)
        signed_velocity.append(velocity[0]*math.cos(math.radians(heading)) +
                               velocity[1]*math.sin(math.radians(heading)))
        previous_frame, previous_time = ident, time
    change = sum((b-a+180) % 360-180 for a, b in zip(headings, headings[1:]))
    orientation = (headings[-1]-headings[0]+180) % 360-180
    path = sum(math.dist(a, b) for a, b in zip(centers, centers[1:]))
    reverse = any(v < -.2 for v in signed_velocity)
    reversal = abs(change) >= 150 and abs(orientation) >= 150 and path >= 5
    return {"status": "met" if reversal and reverse else "not_met",
            "sample_count": expected, "first_frame": mapping[0]["native_frame"],
            "last_frame": mapping[-1]["native_frame"],
            "heading_change_deg": change,
            "endpoint_orientation_change_deg": orientation,
            "sampled_body_path_m": path, "reverse_motion_observed": reverse,
            "engineering_reversal_observed": reversal,
            "criterion": "source joined 150-degree reversal, 5-m body path and signed reverse motion; engineering only"}


def audit(attempt: Path, case_id: str, *, diagnostic: bool = False) -> dict:
    attempt = attempt.resolve()
    require(case_id.endswith(("__below_500_ft", "__at_500_ft", "__above_500_ft")),
            "Unknown exact C104538 case")
    hashes = {name: sha(attempt/name) for name in SOURCES
              if (attempt/name).is_file()}
    missing = sorted(set(SOURCES)-set(hashes))
    base = {"format": "c104538-independent-physical-motion-v1",
            "case_id": case_id, "source_sha256": hashes,
            "missing_sources": missing, "diagnostic_fixture": diagnostic,
            "physical_acceptance_claimed": False, "legal_verdict_claimed": False,
            "two_direction_original_pixel_visibility_proven": False}
    if missing:
        return dict(base, motion_status="unverified", native_motion_status="unverified",
                    source_shaped_motion_status="unverified", maneuver_completed=False,
                    measured=None)
    config, provenance = (read(attempt/name) for name in
                          ("config.json", "acquisition-provenance.json"))
    require(config["case_id"] == case_id, "Attempt selects another case")
    if diagnostic:
        require(provenance.get("diagnostic_fixture") is True and
                provenance.get("provenance_kind") != "native",
                "Diagnostic mode needs explicit synthetic provenance")
    else:
        require(provenance.get("diagnostic_fixture") is False and
                provenance.get("provenance_kind") == "native",
                "Synthetic source cannot prove original Native motion")
        seal_path, exit_path = attempt/"capture-seal.json", attempt/"native-exit.json"
        require(seal_path.is_file() and exit_path.is_file(),
                "Original Native capture seal and exit required")
        seal, exit_record = read(seal_path), read(exit_path)
        require(seal.get("format") == "worker-sealed-capture" and
                seal.get("provenance_kind") == "native" and
                seal.get("diagnostic_fixture") is False and
                seal.get("frames") == int(config["duration_s"]*config["rate_hz"]) and
                seal.get("events") == ["capture_finished", "encoders_closed",
                                       "restoration_verified"] and
                exit_record.get("event") == "native_exit" and
                exit_record.get("native_process_exit_code") == 0 and
                exit_record.get("capture_seal_sha256") == sha(seal_path),
                "Original Native capture closure differs")
        sealed = seal.get("sources", {})
        require(set(SOURCES+CAMERAS) <= set(sealed) and
                all(attempt in (attempt/name).resolve().parents and
                    (attempt/name).is_file() and sha(attempt/name) == digest
                    for name, digest in sealed.items()),
                "Sealed original source inventory differs")
    history, trace, evidence, mapping = (rows(attempt/name) for name in
        ("native_body_history.jsonl", "trace.jsonl", "capture/evidence.jsonl",
         "video_frames.jsonl"))
    for movement, capture in zip(trace, evidence):
        speed = capture["ego"].get("speed_provenance")
        require((speed == "synthetic_native_sample" and
                 movement.get("speed_provenance") == "synthetic_native_sample") if diagnostic else
                speed != "synthetic_native_sample" and
                movement.get("speed_provenance") != "synthetic_native_sample",
                "Synthetic velocity cannot prove original Native motion")
    expected = int(config["duration_s"]*config["rate_hz"])
    measured = classify(history, trace, evidence, mapping, expected)
    status = measured["status"] if not diagnostic else "unverified"
    return dict(base, motion_status=status, native_motion_status=status,
                source_shaped_motion_status=measured["status"] if diagnostic else None,
                maneuver_completed=status == "met", measured=measured)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", type=Path, required=True)
    parser.add_argument("--case", required=True)
    parser.add_argument("--diagnostic", action="store_true")
    args = parser.parse_args()
    print(json.dumps(audit(args.attempt, args.case, diagnostic=args.diagnostic), indent=2))
