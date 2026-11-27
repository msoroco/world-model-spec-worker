"""Independent exact-case original/diagnostic source and four-camera audit."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess

from school_pass import ASSIGNMENT, case_name, measure_original


VIEWS = ("overview", "approach", "reference_corner", "driver_reference")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def required(root: Path, name: str) -> Path:
    path = root / name
    if not path.is_file() or path.is_symlink():
        raise ValueError("Missing required source: " + name)
    return path


def count_and_decode(path: Path, expected: int) -> None:
    probe = subprocess.run(["ffprobe", "-v", "error", "-count_frames", "-select_streams", "v:0",
                            "-show_entries", "stream=nb_read_frames", "-of", "json", str(path)],
                           capture_output=True, text=True, check=True, timeout=120)
    streams = json.loads(probe.stdout).get("streams", [])
    if len(streams) != 1 or streams[0].get("nb_read_frames") != str(expected):
        raise ValueError("full video frame count differs: " + path.name)
    decoded = subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-i", str(path),
                              "-f", "null", "-"], capture_output=True, text=True, timeout=600)
    if decoded.returncode or decoded.stderr.strip():
        raise ValueError("full original camera decode failed: " + path.name)


def audit(case_id: str, attempt: Path, diagnostic: bool = False) -> dict:
    case_name(case_id)
    attempt = Path(attempt)
    context_path = required(attempt, "context.json")
    trace_path = required(attempt, "original-trace.jsonl")
    receipt_path = required(attempt, "receipt.json")
    camera_path = required(attempt, "cameras.json")
    context = json.loads(context_path.read_text())
    receipt = json.loads(receipt_path.read_text())
    if context.get("case_id") != case_id or receipt.get("case_id") != case_id or receipt.get("assignment_id") != ASSIGNMENT:
        raise ValueError("exact school-pass source identity differs")
    for field, path in (("context_sha256", context_path), ("trace_sha256", trace_path),
                        ("camera_manifest_sha256", camera_path)):
        if receipt.get(field) != sha(path):
            raise ValueError("sealed school-pass source changed: " + path.name)
    rows = [json.loads(line) for line in trace_path.read_text().splitlines()]
    expected = 9 if diagnostic else 900
    if len(rows) != expected or receipt.get("frame_count", expected) != expected:
        raise ValueError("original school-pass frame count differs")
    cameras = json.loads(camera_path.read_text())
    if diagnostic:
        provenance = json.loads(required(attempt, "fixture-provenance.json").read_text())
        if provenance.get("diagnostic_fixture") is not True or receipt.get("source_kind") != "synthetic_diagnostic_fixture":
            raise ValueError("diagnostic-only provenance required")
        report = json.loads(required(attempt, "analysis-report.json").read_text())
        if report.get("case_id") != case_id or report.get("diagnostic_fixture") is not True or report.get("legal_verdict_claimed") is not False:
            raise ValueError("diagnostic analysis provenance differs")
        source_set = {"context.json", "original-trace.jsonl", "receipt.json", "cameras.json"}
        for measured in report.get("measurements", {}).values():
            if set(measured.get("sources", {})) != source_set or any(measured["sources"][name] != sha(attempt / name) for name in source_set):
                raise ValueError("diagnostic selected measurement sources differ")
        measured = {"diagnostic_frames": expected, "physical_pass": "unverified"}
    else:
        if receipt.get("source_kind") != "original_native_capture" or (attempt / "fixture-provenance.json").exists():
            raise ValueError("original Native provenance required")
        pipeline = json.loads(required(attempt, "capture/manifest.json").read_text())
        if pipeline.get("extraction_confirmed") is not True or pipeline.get("frames") != expected:
            raise ValueError("pinned original capture graph/evidence incomplete")
        required(attempt, "capture/evidence.jsonl")
        required(attempt, "road.xodr")
        measured = measure_original(rows, context, case_id)
    if diagnostic:
        if set(cameras.get("views", [])) != set(VIEWS):
            raise ValueError("four diagnostic camera sources missing")
        source_receipt = json.loads(required(attempt, "four-view-receipt.json").read_text())
        streams = source_receipt.get("sources", {})
        if set(streams) != set(VIEWS):
            raise ValueError("four-view diagnostic source seal missing")
        for view in VIEWS:
            path = required(attempt, view + ".mkv")
            if streams[view] != sha(path):
                raise ValueError("diagnostic camera source changed: " + view)
            count_and_decode(path, expected)
    else:
        streams = cameras.get("streams", {})
        if set(streams) != set(VIEWS):
            raise ValueError("four original camera sources missing")
        for view in VIEWS:
            path = required(attempt, view + ".mkv")
            if streams[view].get("sha256") != sha(path):
                raise ValueError("original camera source changed: " + view)
            count_and_decode(path, expected)
    return {"format": "worker-delivery-audit-diagnostic" if diagnostic else "worker-delivery-audit-preparation",
            "assignment_id": ASSIGNMENT, "case_id": case_id,
            "source_kind": receipt["source_kind"], "frame_count": expected,
            "source_hashes": {name: sha(path) for name, path in
                              (("context.json", context_path), ("original-trace.jsonl", trace_path),
                               ("receipt.json", receipt_path), ("cameras.json", camera_path))},
            "checks": ["native_source", "all_participants", "time_join", "full_video_decode",
                       "actual_pixels", "physical_completion"],
            "measurement": measured, "physical_acceptance": "unverified",
            "legal_judgment": "unresolved", "diagnostic_fixture": diagnostic}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--diagnostic", action="store_true")
    parser.add_argument("--case", required=True)
    parser.add_argument("--attempt", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.write_text(json.dumps(audit(args.case, args.attempt, args.diagnostic),
                                     indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
