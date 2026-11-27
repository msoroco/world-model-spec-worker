"""Independent original-source delivery audit for one exact bridge approach.

A diagnostic protocol check verifies software joins only. Native acceptance requires
separate original pixel and physical review; no legal judgment is produced.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from native_scene import ASSIGNMENT, CASE_VARIANTS, CAMERAS


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]


def audit(attempt, case_id, output, *, diagnostic_protocol=False):
    from worker_exchange.media import audit as decode
    attempt, output = Path(attempt).resolve(), Path(output).resolve()
    if output.exists():
        raise ValueError("retain prior delivery audit output")
    if not case_id.startswith(ASSIGNMENT + "__") or case_id.removeprefix(ASSIGNMENT + "__") not in CASE_VARIANTS:
        raise ValueError("exact delivery case mismatch")
    required = ("bridge-history.jsonl", "video_frames.jsonl", "trace.jsonl",
                "road-context.json", "native-result.json", "analysis-report.json", "result.json")
    for name in required:
        if not (attempt / name).is_file():
            raise ValueError("missing original delivery evidence: " + name)
    provenance = read(attempt / "acquisition-provenance.json")
    is_fixture = provenance.get("diagnostic_fixture") is True
    if diagnostic_protocol:
        if not is_fixture:
            raise ValueError("diagnostic protocol requires explicit synthetic provenance")
    elif is_fixture:
        raise ValueError("synthetic fixture cannot be accepted as Native delivery")
    else:
        seal = read(attempt / "capture-seal.json")
        if seal.get("events") != ["capture_finished", "encoders_closed", "restoration_verified"]:
            raise ValueError("Native closure order missing")
        for name, expected in seal.get("sources", {}).items():
            if sha(attempt / name) != expected:
                raise ValueError("sealed original source changed: " + name)
        native_exit = read(attempt / "native-exit.json")
        if native_exit.get("capture_seal_sha256") != sha(attempt / "capture-seal.json"):
            raise ValueError("Native exit source binding changed")
        owner = read(attempt / "owner-release-attested.json")
        if owner.get("event") != "owner_released" or owner.get("operator_attested") is not True:
            raise ValueError("operator owner release missing")
    history = rows(attempt / "bridge-history.jsonl")
    mapping = rows(attempt / "video_frames.jsonl")
    trace = rows(attempt / "trace.jsonl")
    if not history or len(history) != len(mapping) or len(history) != len(trace):
        raise ValueError("original body/trace/frame count mismatch")
    for index, (body, frame, point) in enumerate(zip(history, mapping, trace)):
        if body.get("original_frame") != index or body.get("carla_frame") != frame.get("carla_frame") or point.get("frame") != frame.get("carla_frame") or abs(body.get("time_s", -1)-frame.get("time_s", -2)) > 1e-6:
            raise ValueError("original time join mismatch")
        if "ego" not in body.get("actors", {}):
            raise ValueError("required bridge participant absent")
    report = read(attempt / "analysis-report.json")
    result = read(attempt / "result.json")
    if report.get("case_id") != case_id or result.get("case_id") != case_id or not report.get("analysis_complete"):
        raise ValueError("saved analysis identity or completion missing")
    for value in report.get("measurements", {}).values():
        for name, expected in value.get("sources", {}).items():
            if sha(attempt / name) != expected:
                raise ValueError("source-bound measurement changed: " + name)
    measured = report["measurements"]["measure_bridge_approach"]["value"]
    if measured.get("one_way_highway") != case_id.endswith("one_way_exception"):
        raise ValueError("measured one-way status differs from exact case")
    samples = measured.get("per_frame", [])
    if not samples or not any(s["bridge_distance_front_m"] >= 0 for s in samples):
        raise ValueError("bridge approach body history missing")
    if case_id.endswith("right_side_within_100ft"):
        if any(s["left_of_center_body"] for s in samples):
            raise ValueError("right-side reference crossed centerline")
    elif not any(s["left_of_center_body"] for s in samples):
        raise ValueError("left-of-center bridge approach never measured")
    if not diagnostic_protocol:
        physical = result.get("physical_checks", {})
        if physical.get("setup", {}).get("status") != "met" or physical.get("attempt", {}).get("status") != "met":
            raise ValueError("original physical setup or motion unconfirmed")
    decoded = {}
    output.parent.mkdir(parents=True, exist_ok=True)
    for name in CAMERAS:
        video = attempt / (name + ".mkv")
        if not video.is_file():
            raise ValueError("original camera missing: " + name)
        receipt = output.with_name(output.stem + "-decode-" + name + ".json")
        decoded[name] = decode(video, len(mapping), mapping_sha256=sha(attempt / "video_frames.jsonl"), receipt=receipt)
    if not diagnostic_protocol:
        pixel = read(attempt / "pixel-review.json")
        if pixel.get("case_id") != case_id or pixel.get("reviewer") in (None, "") or pixel.get("actual_pixels_visible") is not True or pixel.get("physical_completion_reviewed") is not True:
            raise ValueError("independent actual-pixel and physical review missing")
        if pixel.get("video_sha256") != {name:sha(attempt / (name + ".mkv")) for name in CAMERAS}:
            raise ValueError("pixel review references different original footage")
    audit_record = {"format":"worker-delivery-audit-diagnostic" if diagnostic_protocol else "worker-delivery-audit",
                    "case_id":case_id,"original_frames":len(mapping),
                    "original_source_sha256":{name:sha(attempt / name) for name in required},
                    "decoded_video_sha256":{name:item["video_sha256"] for name,item in decoded.items()},
                    "checks":["native_source","all_participants","time_join","full_video_decode",
                              "actual_pixels","physical_completion"],
                    "actual_pixels_reviewed":not diagnostic_protocol,
                    "physical_acceptance_claimed":False,"legal_judgment":"unresolved"}
    output.write_text(json.dumps(audit_record, indent=2) + "\n")
    return audit_record


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", type=Path, required=True)
    parser.add_argument("--case", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--diagnostic-protocol", action="store_true")
    args = parser.parse_args()
    result = audit(args.attempt,args.case,args.output,diagnostic_protocol=args.diagnostic_protocol)
    print(json.dumps({"case_id":result["case_id"],"frames":result["original_frames"],
                      "physical_acceptance_claimed":False},sort_keys=True))


if __name__ == "__main__":main()
