"""Independent original-source acceptance audit for NRS 484B.307(9)(a)."""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path

from saved_turn import audit_saved_attempt

CAMERAS = ("overview", "approach", "reference_corner", "driver_reference")
REQUIRED = ("manifest.json", "telemetry.json", "frame_map.json", "site.json",
            "camera_profile.json", "trace.jsonl", "video_frames.jsonl",
            "body_history.jsonl", "road.xodr", "carla_recorder.log")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def lines(path):
    return [json.loads(row) for row in Path(path).read_text().splitlines() if row.strip()]


def require(condition, message):
    if not condition:
        raise ValueError(message)


def audit(attempt, case_id, *, diagnostic=False):
    attempt = Path(attempt).resolve()
    config = read(attempt / "config.json")
    require(config.get("selected_case_id") == case_id,
            "independent audit selects another exact case")
    manifest = attempt / "manifest.json"
    source = audit_saved_attempt(attempt, {"path": "manifest.json", "sha256": sha(manifest)},
                                 expected_frames=600, diagnostic=diagnostic)
    require(source["original_frames"] == 600 and
            sum(view["frames"] for view in source["decoded_cameras"].values()) == 2400,
            "all original camera pixels were not decoded")
    if diagnostic:
        return {"format": "worker-delivery-audit-diagnostic", "case_id": case_id,
                "passed": True, "decoded_original_png_frames": 2400,
                "physical_acceptance_claimed": False, "legal_verdict": None}
    require(not (attempt / "fixture-provenance.json").exists(),
            "diagnostic fixture cannot establish Native delivery")
    provenance = read(attempt / "acquisition-provenance.json")
    require(provenance.get("provenance_kind") == "native" and
            provenance.get("diagnostic_fixture") is False,
            "original Native provenance missing")
    seal = read(attempt / "capture-seal.json")
    require(seal.get("events") == ["capture_finished", "encoders_closed", "restoration_verified"]
            and seal.get("restoration", {}).get("restored") is True
            and seal.get("frames") == 600,
            "Native capture lifecycle incomplete")
    required = set(REQUIRED) | {name + ".mkv" for name in CAMERAS}
    require(required <= set(seal.get("sources", {})), "sealed original source missing")
    for name, digest in seal["sources"].items():
        path = (attempt / name).resolve()
        require(path.is_relative_to(attempt) and path.is_file() and sha(path) == digest,
                "sealed original missing or changed: " + name)
    native_exit = read(attempt / "native-exit.json")
    require(native_exit.get("event") == "native_exit" and
            native_exit.get("capture_seal_sha256") == sha(attempt / "capture-seal.json"),
            "Native process exit not bound to seal")
    owner = read(attempt / "owner-release.json")
    require(owner.get("event") == "owner_released" and
            owner.get("operator_attested") is True and
            owner.get("native_exit_sha256") == sha(attempt / "native-exit.json"),
            "owner release not bound to Native exit")
    trace, mapping, body = (lines(attempt / name) for name in
                            ("trace.jsonl", "video_frames.jsonl", "body_history.jsonl"))
    original_map = read(attempt / "frame_map.json")
    require(len(trace) == len(mapping) == len(body) == len(original_map) == 600,
            "original trace, frame map or body history incomplete")
    for index, (motion, frame, vertices, original) in enumerate(zip(trace, mapping, body, original_map)):
        require(frame.get("video_frame") == index and
                frame.get("native_frame") == original.get("native_frame") == motion.get("frame") == vertices.get("frame") and
                abs(frame.get("time_s", -1) - original.get("native_elapsed_s", -2)) <= .001 and
                abs(frame.get("time_s", -1) - motion.get("time_s", -2)) <= .001 and
                abs(frame.get("time_s", -1) - vertices.get("time_s", -2)) <= .001,
                "original Native trace/camera/body timestamp join differs")
    for camera in CAMERAS:
        video = attempt / (camera + ".mkv")
        probe = subprocess.run(["ffprobe", "-v", "error", "-count_frames",
            "-select_streams", "v:0", "-show_entries", "stream=nb_read_frames",
            "-of", "default=nokey=1:noprint_wrappers=1", str(video)],
            check=True, text=True, capture_output=True)
        require(probe.stdout.strip() == "600", "full original video decode incomplete: " + camera)
    result = read(attempt / "result.json")
    require(result.get("case_id") == case_id and
            all(result.get(key) is True for key in
                ("setup_confirmed", "behavior_attempted", "maneuver_completed")) and
            result.get("physical_checks", {}).get("maneuver", {}).get("status") == "met" and
            result.get("realized_observables"),
            "physical completion not established by saved original result")
    require("legal_verdict" not in result and "compliant" not in result,
            "delivery audit cannot issue a legal verdict")
    return {"format": "worker-delivery-audit", "case_id": case_id,
            "passed": True, "checks": {key: True for key in
                ("native_source", "all_participants", "time_join", "full_video_decode",
                 "actual_pixels", "physical_completion")},
            "source_result_sha256": sha(attempt / "result.json"),
            "frame_map_sha256": sha(attempt / "video_frames.jsonl"),
            "decoded_original_png_frames": 2400, "decoded_original_video_frames": 2400,
            "legal_verdict": None}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", required=True)
    parser.add_argument("--attempt", type=Path, required=True)
    parser.add_argument("--diagnostic", action="store_true")
    args = parser.parse_args()
    print(json.dumps(audit(args.attempt, args.case, diagnostic=args.diagnostic), indent=2))
