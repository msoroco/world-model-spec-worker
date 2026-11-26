"""Independent source audit for bounded diagnostics and exact original index jobs."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess

from delivery_audit import audit as audit_original
from school_scene_construction import ASSIGNMENT


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def diagnostic(case_id: str, attempt: Path) -> dict:
    attempt = Path(attempt)
    plan = json.loads((Path(__file__).resolve().parent / "case-plan.json").read_text())
    if case_id not in {row["case_id"] for row in plan["cases"]}:
        raise ValueError("unknown exact school-zone case")
    context = attempt / "context.json"
    if not context.is_file():
        raise ValueError("Missing required source: context.json")
    provenance = json.loads((attempt / "fixture-provenance.json").read_text())
    receipt = json.loads((attempt / "receipt.json").read_text())
    report = json.loads((attempt / "analysis-report.json").read_text())
    if (provenance.get("diagnostic_fixture") is not True or
            receipt.get("source_kind") != "synthetic_diagnostic_fixture" or
            receipt.get("case_id") != case_id or report.get("case_id") != case_id or
            report.get("diagnostic_fixture") is not True or
            report.get("legal_verdict_claimed") is not False):
        raise ValueError("school-zone diagnostic identity or provenance changed")
    sources = report["measurements"]["school_zone_uturn_context"]["sources"]
    expected = {"context.json", "original-trace.jsonl", "receipt.json", "cameras.json"}
    if set(sources) != expected:
        raise ValueError("diagnostic source inventory differs")
    for name, digest in sources.items():
        path = attempt / name
        if not path.is_file() or sha(path) != digest:
            raise ValueError("diagnostic source changed: " + name)
    for name, key in (("context.json", "context_sha256"),
                      ("original-trace.jsonl", "trace_sha256"),
                      ("cameras.json", "camera_manifest_sha256")):
        if receipt.get(key) != sha(attempt / name):
            raise ValueError("diagnostic receipt source changed: " + name)
    cameras = json.loads((attempt / "cameras.json").read_text())
    streams = json.loads((attempt / "four-view-receipt.json").read_text()).get("sources", {})
    if (set(cameras.get("views", [])) != {"overview", "approach", "reference_corner", "driver_reference"} or
            set(streams) != set(cameras["views"])):
        raise ValueError("four diagnostic camera sources required")
    for view, digest in streams.items():
        path = attempt / (view + ".mkv")
        if not path.is_file() or sha(path) != digest:
            raise ValueError("diagnostic camera source changed: " + view)
        probe = subprocess.run(["ffprobe", "-v", "error", "-count_frames", "-select_streams", "v:0",
                                "-show_entries", "stream=nb_read_frames", "-of", "json", str(path)],
                               text=True, capture_output=True, check=True)
        frames = json.loads(probe.stdout)["streams"][0]["nb_read_frames"]
        if int(frames) != provenance.get("frames"):
            raise ValueError("diagnostic camera frame count differs: " + view)
    return {"assignment_id": ASSIGNMENT, "case_id": case_id,
            "source_kind": "synthetic_diagnostic_fixture", "diagnostic_fixture": True,
            "positive_source_bindings": sources, "four_video_sources_decoded": True,
            "physical_acceptance": "unverified", "legal_judgment": "unresolved"}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--index", type=Path)
    parser.add_argument("--case", required=True)
    parser.add_argument("--attempt", type=Path)
    parser.add_argument("--diagnostic", action="store_true")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.diagnostic:
        if args.index or not args.attempt:
            raise ValueError("one exact diagnostic attempt required")
        result = diagnostic(args.case, args.attempt)
    else:
        if not args.index or args.attempt:
            raise ValueError("original six-case delivery index required")
        result = audit_original(args.index)
        if args.case not in json.loads(args.index.read_text()).get("cases", {}):
            raise ValueError("exact original delivery case missing")
        result["requested_case_id"] = args.case
    args.output.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n")


if __name__ == "__main__":
    main()
