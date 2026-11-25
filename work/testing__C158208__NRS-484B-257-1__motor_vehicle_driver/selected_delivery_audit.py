"""Independently check one selected saved analysis against its original sources."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess

from camera_sources import CAMERAS, DIMENSIONS, audit_camera_sources
from source_tick_capture import verify_seal

ASSIGNMENT = "testing__C158208__NRS-484B-257-1__motor_vehicle_driver"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rows(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def video(path: Path, frames: int, dimensions: tuple[int, int]) -> dict:
    probe = subprocess.run(["ffprobe", "-v", "error", "-count_frames", "-select_streams", "v:0",
                            "-show_entries", "stream=width,height,nb_read_frames,r_frame_rate",
                            "-of", "json", str(path)], capture_output=True, text=True, check=True)
    stream = json.loads(probe.stdout)["streams"][0]
    if ((stream["width"], stream["height"]) != dimensions or
            stream["r_frame_rate"] != "20/1" or int(stream["nb_read_frames"]) != frames):
        raise ValueError("selected video dimensions, fps or frames differ: " + path.name)
    decoded = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-f", "null", "-"],
                             capture_output=True, text=True)
    if decoded.returncode:
        raise ValueError("selected video full decode failed: " + path.name)
    return {"path": path.name, "sha256": sha(path), "frames": frames,
            "dimensions": list(dimensions)}


def audit(stage: Path, *, case_id: str, diagnostic_fixture: bool) -> dict:
    stage = Path(stage)
    if not case_id.startswith(ASSIGNMENT + "__"):
        raise ValueError("selected delivery case outside assignment")
    packet = verify_seal(stage)
    sample_count = len(packet["samples"])
    if not diagnostic_fixture and sample_count != 900:
        raise ValueError("original production capture needs 900 sealed ticks")
    identity = json.loads((stage / "capture-identity.json").read_text())
    if identity.get("case_id") != case_id or identity.get("assignment_id") != ASSIGNMENT:
        raise ValueError("selected delivery identity differs")
    if identity.get("provenance_kind") != ("synthetic_fixture" if diagnostic_fixture else "original_capture"):
        raise ValueError("selected delivery provenance differs")
    report_path = stage / "analysis-report.json"
    report = json.loads(report_path.read_text())
    if (report.get("case_id") != case_id or report.get("diagnostic_fixture") is not diagnostic_fixture
            or report.get("legal_judgment") is not None):
        raise ValueError("selected delivery report identity or judgment differs")
    measurements = report.get("measurements", {})
    if set(measurements) != {"nearest_view_history", "governing_control_context"}:
        raise ValueError("selected delivery measurement inventory differs")
    for key, item in measurements.items():
        if item.get("case_id") != case_id or item.get("diagnostic_fixture") is not diagnostic_fixture:
            raise ValueError("selected measurement identity differs: " + key)
        for name, digest in item.get("sources", {}).items():
            path = stage / name
            if not path.is_file() or sha(path) != digest:
                raise ValueError("selected measurement source differs: " + name)
    result = json.loads((stage / "result.json").read_text())
    if result.get("case_id") != case_id or result.get("diagnostic_fixture") is not diagnostic_fixture:
        raise ValueError("selected Native result identity differs")
    trace = rows(stage / result["trace_reference"])
    mapping = rows(stage / result["video_frame_map_reference"])
    if len(trace) != sample_count or len(mapping) != sample_count:
        raise ValueError("selected trace/video frame count differs")
    for sample, tick, frame in zip(packet["samples"], trace, mapping):
        if (tick["frame"] != sample["frame"] or frame["carla_frame"] != sample["frame"] or
                tick["time_s"] != sample["time_s"] or frame["time_s"] != sample["time_s"]):
            raise ValueError("selected trace/video timestamp join differs")
    if not diagnostic_fixture:
        audit_camera_sources(stage)
    sources = {}
    if len(result["video_references"]) != 4:
        raise ValueError("four exact camera sources required")
    for name, ref in zip(CAMERAS, result["video_references"]):
        if ref != name + ".mkv":
            raise ValueError("selected camera order differs")
        sources[name] = video(stage / ref, sample_count, DIMENSIONS[name])
    return {"format": "c158208-selected-delivery-audit-v1", "case_id": case_id,
            "diagnostic_fixture": diagnostic_fixture, "source_frames": sample_count,
            "report_sha256": sha(report_path), "result_sha256": sha(stage / "result.json"),
            "camera_sources": sources, "checks": ["sealed_ticks", "source_hashes",
                "trace_frame_join", "four_camera_full_decode", "unresolved_legal_judgment"],
            "physical_acceptance_claimed": False, "legal_acceptance_claimed": False}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage", type=Path, required=True)
    parser.add_argument("--case", required=True)
    parser.add_argument("--diagnostic-fixture", action="store_true")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("audit output already exists")
    result = audit(args.stage, case_id=args.case, diagnostic_fixture=args.diagnostic_fixture)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(result["case_id"])
