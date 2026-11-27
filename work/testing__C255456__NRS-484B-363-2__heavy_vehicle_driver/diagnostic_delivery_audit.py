"""Independent CPU audit of one exact diagnostic package; no physical acceptance."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

from crossing_scene import ASSIGNMENT

VIEWS = ("overview", "approach", "reference_corner", "driver_reference")
SOURCES = ("context.json", "original-trace.jsonl", "receipt.json", "cameras.json")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def audit(case_id, attempt):
    root = Path(attempt)
    if not case_id.startswith(ASSIGNMENT + "__"):
        raise ValueError("unknown exact heavy-vehicle case")
    for name in SOURCES:
        if not (root / name).is_file():
            raise ValueError("Missing required source: " + name)
    receipt = json.loads((root / "receipt.json").read_text())
    report = json.loads((root / "analysis-report.json").read_text())
    result = json.loads((root / "result.json").read_text())
    provenance = json.loads((root / "fixture-provenance.json").read_text())
    if (receipt.get("case_id") != case_id or report.get("case_id") != case_id or
            result.get("case_id") != case_id or
            provenance.get("diagnostic_fixture") is not True or
            receipt.get("source_kind") != "synthetic_diagnostic_fixture" or
            report.get("diagnostic_fixture") is not True or
            result.get("physical_acceptance_claimed") is not False or
            report.get("legal_verdict_claimed") is not False):
        raise ValueError("diagnostic heavy-vehicle source identity changed")
    hashes = {name: sha(root / name) for name in SOURCES}
    if (receipt.get("context_sha256") != hashes["context.json"] or
            receipt.get("trace_sha256") != hashes["original-trace.jsonl"] or
            receipt.get("camera_manifest_sha256") != hashes["cameras.json"]):
        raise ValueError("diagnostic heavy-vehicle source seal changed")
    if not report.get("measurements") or any(
            value.get("sources") != hashes for value in report["measurements"].values()):
        raise ValueError("saved diagnostic measurement source changed")
    camera = json.loads((root / "cameras.json").read_text())
    four = json.loads((root / "four-view-receipt.json").read_text())
    if (camera.get("case_id") != case_id or camera.get("views") != list(VIEWS) or
            camera.get("frame_count") != provenance.get("frames") or
            set(four.get("sources", {})) != set(VIEWS)):
        raise ValueError("four diagnostic camera sources incomplete")
    for view in VIEWS:
        path = root / (view + ".mkv")
        if sha(path) != four["sources"][view]:
            raise ValueError("diagnostic camera bytes changed: " + view)
        probe = subprocess.run(["ffprobe", "-v", "error", "-count_frames",
                                "-select_streams", "v:0", "-show_entries",
                                "stream=nb_read_frames", "-of", "json", str(path)],
                               capture_output=True, text=True, check=True)
        frames = json.loads(probe.stdout)["streams"][0]["nb_read_frames"]
        if int(frames) != camera["frame_count"]:
            raise ValueError("diagnostic camera frame count changed: " + view)
    trace = [json.loads(line) for line in (root / "trace.jsonl").read_text().splitlines()]
    mapping = [json.loads(line) for line in (root / "video_frames.jsonl").read_text().splitlines()]
    if len(trace) != camera["frame_count"] or len(mapping) != len(trace) or any(
            t["frame"] != m["carla_frame"] or t["time_s"] != m["time_s"]
            for t, m in zip(trace, mapping)):
        raise ValueError("diagnostic saved trace and video time join changed")
    return {"assignment_id": ASSIGNMENT, "case_id": case_id,
            "source_kind": "synthetic_diagnostic_fixture", "diagnostic_fixture": True,
            "source_bindings": hashes, "four_video_sources_decoded": True,
            "saved_time_join_checked": True, "physical_acceptance": "unverified",
            "legal_judgment": "unresolved"}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", required=True)
    parser.add_argument("--attempt", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    Path(args.output).write_text(json.dumps(audit(args.case, args.attempt), sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
