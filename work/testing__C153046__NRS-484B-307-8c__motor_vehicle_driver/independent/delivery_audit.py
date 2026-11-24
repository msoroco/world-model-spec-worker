"""Independent C153046 original-source delivery gate.

Actual CLI acceptance requires a sealed Native attempt and a current pinned
full-decode receipt. Synthetic unit protocols use allow_diagnostic=True and
return a different format with no acceptance claim.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from build_case_plan import AID, KINDS
from saved_observation_audit import audit as audit_observations

PINNED_MEDIA = next((parent / "runtime" / "scenario_pipeline" / "worker_exchange" / "media.py"
                     for parent in Path(__file__).resolve().parents
                     if (parent / "runtime" / "scenario_pipeline" / "worker_exchange" / "media.py").is_file()),
                    None)
if PINNED_MEDIA is None:
    raise ValueError("pinned media auditor source unavailable")

CHECKS = ("native_source", "all_participants", "time_join", "full_video_decode",
          "actual_pixels", "physical_completion", "observation_replay")
VIEWS = {"overview", "approach", "reference_corner", "driver_reference"}
CAMERAS = {name + ".mkv" for name in VIEWS}
SOURCES = {"site.json", "trace.jsonl", "video_frames.jsonl", "raw.mkv", *CAMERAS}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path: Path) -> dict:
    return json.loads(path.read_text())


def verify(case_id: str, attempt: Path, *, allow_diagnostic: bool = False) -> dict:
    attempt = Path(attempt).resolve()
    if not case_id.startswith(AID + "__") or case_id[len(AID) + 2:] not in KINDS:
        raise ValueError("unknown exact case")
    suffix = case_id[len(AID) + 2:]
    seal = read(attempt / "source-seal.json")
    diagnostic = seal.get("diagnostic_fixture") is True
    if diagnostic and not allow_diagnostic:
        raise ValueError("diagnostic fixture cannot pass delivery acceptance")
    if seal.get("case_id") != case_id or seal.get("provenance_kind") != "native" or not SOURCES <= set(seal.get("source_hashes", {})):
        raise ValueError("sealed Native source inventory incomplete")
    for name, digest in seal["source_hashes"].items():
        path = (attempt / name).resolve()
        if not path.is_relative_to(attempt) or not path.is_file() or sha(path) != digest:
            raise ValueError("sealed original source changed: " + name)
    trace = [json.loads(line) for line in (attempt / "trace.jsonl").read_text().splitlines() if line.strip()]
    mapping = [json.loads(line) for line in (attempt / "video_frames.jsonl").read_text().splitlines() if line.strip()]
    replay = audit_observations(attempt / "site.json", attempt / "trace.jsonl", case_id,
                                expected_frames=len(trace) if diagnostic else 600)
    measurement = read(attempt / "measurement.json")
    if (len(trace) < 2 or len(mapping) != len(trace) or
            measurement.get("case_id") != case_id or
            measurement.get("format") != "c153046-source-bound-measurement-draft" or
            measurement.get("trace_sha256") != sha(attempt / "trace.jsonl") or
            measurement.get("site_packet_sha256") != sha(attempt / "site.json") or
            measurement.get("frames") != len(trace)):
        raise ValueError("source-bound measurement missing or stale")
    for index, (row, frame) in enumerate(zip(trace, mapping)):
        native = row.get("native_frame", {})
        if (frame.get("video_frame") != index or frame.get("carla_frame") != native.get("frame") or
                abs(frame.get("time_s", -1) - native.get("time_s", -2)) > 1e-6):
            raise ValueError("original video/frame/trace time join differs")
    physical = read(attempt / "result.json")
    if (physical.get("case_id") != case_id or physical.get("provenance_kind") != "native" or
            physical.get("diagnostic_fixture") is not diagnostic or
            physical.get("setup_confirmed") is not True or
            physical.get("maneuver_completed") is not True or
            physical.get("measurement_sha256") != sha(attempt / "measurement.json") or
            physical.get("physical_checks", {}).get("setup") != "met" or
            physical.get("physical_checks", {}).get("maneuver") != "met"):
        raise ValueError("original physical completion unverified")
    decode = read(attempt / "source-decode.json")
    auditor = Path(decode.get("auditor_path", ""))
    if (decode.get("format") != "source-decode" or decode.get("passed") is not True or
            not auditor.is_file() or decode.get("auditor_sha256") != sha(auditor) or
            (not diagnostic and auditor.resolve() != PINNED_MEDIA.resolve()) or
            decode.get("video_sha256") != sha(attempt / "raw.mkv") or
            decode.get("mapping_sha256") != sha(attempt / "video_frames.jsonl") or
            decode.get("frames") != len(trace) or
            decode.get("checks", {}).get("frame_count") != "all-decoded-frames"):
        raise ValueError("full video decode receipt missing or stale")
    composition = read(attempt / "four-view-receipt.json")
    if (composition.get("format") != "synchronized-four-view" or
            composition.get("frames") != len(trace) or
            composition.get("frame_map_sha256") != sha(attempt / "video_frames.jsonl") or
            composition.get("primary_sha256") != sha(attempt / "raw.mkv") or
            composition.get("sources") != {name.removesuffix(".mkv"): sha(attempt / name)
                                          for name in CAMERAS}):
        raise ValueError("four original camera sources unverified")
    pixels = read(attempt / "pixel-review.json")
    required = {"red_alone_signal", "stop_boundary", "approach_lane", "receiving_road"}
    if "pedestrian" in suffix:
        required |= {"pedestrian_body", "pedestrian_yield_response"}
    if "traffic" in suffix:
        required |= {"traffic_body", "traffic_yield_response"}
    if (pixels.get("format") != "worker-original-pixel-review" or
            pixels.get("case_id") != case_id or pixels.get("diagnostic_fixture") is not diagnostic or
            not pixels.get("reviewer") or pixels.get("video_sha256") != sha(attempt / "raw.mkv") or
            pixels.get("frame_map_sha256") != sha(attempt / "video_frames.jsonl") or
            pixels.get("measurement_sha256") != sha(attempt / "measurement.json")):
        raise ValueError("original pixel review missing or stale")
    for key in required:
        observation = pixels.get("observations", {}).get(key, {})
        if (observation.get("visible") is not True or
                type(observation.get("frame")) is not int or
                not 0 <= observation["frame"] < len(trace) or
                observation.get("view") not in VIEWS or not observation.get("description")):
            raise ValueError("actual pixels unverified: " + key)
    return {"format": "c153046-diagnostic-delivery-protocol" if diagnostic else "worker-delivery-audit",
            "passed": True, "case_id": case_id, "checks": {key: True for key in CHECKS},
            "frames": len(trace), "video": "raw.mkv", "video_sha256": sha(attempt / "raw.mkv"),
            "trace": "trace.jsonl", "trace_sha256": sha(attempt / "trace.jsonl"),
            "frame_map_sha256": sha(attempt / "video_frames.jsonl"),
            "source_result_sha256": sha(attempt / "result.json"),
            "observation_replay": replay,
            "source_decode_receipt_path": str((attempt / "source-decode.json").resolve()),
            "source_decode_receipt_sha256": sha(attempt / "source-decode.json"),
            "source_decode_auditor_sha256": sha(PINNED_MEDIA),
            "auditor_path": str(Path(__file__).resolve()),
            "auditor_sha256": sha(Path(__file__)),
            "physical_acceptance_claimed": not diagnostic}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", required=True)
    parser.add_argument("--attempt", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--job-id", required=True)
    parser.add_argument("--attempt-number", required=True, type=int)
    parser.add_argument("--recording-id", required=True)
    args = parser.parse_args()
    output = Path(args.output)
    if output.exists():
        raise ValueError("retain previous independent audit")
    result = verify(args.case, Path(args.attempt))
    if args.attempt_number < 1 or not args.job_id or not args.recording_id:
        raise ValueError("original job, attempt and recording identity required")
    result.update(job_id=args.job_id, attempt=args.attempt_number,
                  recording_id=args.recording_id)
    output.write_text(json.dumps(result, indent=2) + "\n")
    print(result["case_id"], result["passed"])


if __name__ == "__main__":
    main()
