"""Independent exact-case saved-source delivery audit; fixtures never claim acceptance."""
from __future__ import annotations

import argparse
import base64
import hashlib
import io
import json
import subprocess
import zipfile
from pathlib import Path

from officer_motion import measure
from officer_scene import CASES
from officer_site_packet import validate_packet

ASSIGNMENT = "testing__C157964__NRS-484B-257-2__motor_vehicle_driver"
VIEWS = ("overview", "approach", "reference_corner", "driver_reference")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path: Path):
    return json.loads(path.read_text())


def rows(path: Path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def audit(stage: Path, case_id: str, *, diagnostic_fixture: bool) -> dict:
    stage = Path(stage)
    suffix = case_id.removeprefix(ASSIGNMENT + "__")
    case = next((item for item in CASES if item.suffix == suffix), None)
    if case is None or case_id != ASSIGNMENT + "__" + suffix:
        raise ValueError("audit requires one exact officer case")
    config, construction = read(stage / "config.json"), read(stage / "construction.json")
    seal, exit_receipt = read(stage / "capture-seal.json"), read(stage / "native-exit.json")
    report, result = read(stage / "analysis-report.json"), read(stage / "result.json")
    provenance = "synthetic_fixture" if diagnostic_fixture else "native"
    if (config.get("selected_case_id") != case_id or construction.get("case_id") != case_id or
            seal.get("case_id") != case_id or report.get("case_id") != case_id or
            result.get("case_id") != case_id or result.get("provenance_kind") != provenance or
            result.get("diagnostic_fixture") is not diagnostic_fixture):
        raise ValueError("selected case or source provenance differs")
    count = seal.get("frame_count")
    if type(count) is not int or (not 8 <= count <= 20 if diagnostic_fixture else count != 900):
        raise ValueError("original 20 Hz frame count differs")
    if seal.get("events") != ["capture_finished", "encoders_closed", "restoration_verified"]:
        raise ValueError("Native capture lifecycle incomplete")
    if exit_receipt.get("capture_seal_sha256") != sha(stage / "capture-seal.json") or \
            exit_receipt.get("event") != "native_exit":
        raise ValueError("Native owner release differs")
    inventory = seal.get("source_sha256", {})
    if not inventory or any(sha(stage / name) != digest for name, digest in inventory.items()):
        raise ValueError("sealed original source changed")
    site = validate_packet(stage / "original-attempt/site-packet.json", case_id)
    history = read(stage / "original-attempt/history.json")
    frame_map = read(stage / "original-attempt/frame-map.json")
    trace, video_map = rows(stage / "trace.jsonl"), rows(stage / "video_frames.jsonl")
    if any(len(seq) != count for seq in (history, frame_map, trace, video_map)):
        raise ValueError("participant/frame/video join incomplete")
    for index, (sample, mapped, tick, video) in enumerate(zip(history, frame_map, trace, video_map)):
        state = sample.get("state", {})
        if (sample.get("case_id") != case_id or
                not all(state.get(actor, {}).get("id") for actor in ("ego", "other", "officer")) or
                mapped.get("frame") != index or mapped.get("carla_frame") != sample.get("frame") or
                tick.get("frame") != sample.get("frame") or
                video.get("carla_frame") != sample.get("frame") or
                video.get("video_frame") != index or
                any(item.get("time_s") != sample.get("time_s") for item in (mapped, tick, video))):
            raise ValueError("original participants, frame or time join differs")
    for view in VIEWS:
        archive_path = stage / "original-attempt" / (view + ".zip")
        if archive_path.is_file():
            archive_bytes = archive_path.read_bytes()
        elif diagnostic_fixture:
            archive_bytes = base64.b64decode((stage / "original-attempt" /
                                             (view + ".zip.b64")).read_text().strip(), validate=True)
        else:
            raise ValueError("original camera archive missing: " + view)
        with zipfile.ZipFile(io.BytesIO(archive_bytes)) as archive:
            members = [sample["camera_frames"][view]["member"] for sample in history]
            if archive.namelist() != members:
                raise ValueError("camera frame inventory differs: " + view)
            for member, sample in zip(members, history):
                raw = archive.read(member)
                if not raw.startswith(b"\x89PNG\r\n\x1a\n") or \
                        hashlib.sha256(raw).hexdigest() != sample["camera_frames"][view]["sha256"]:
                    raise ValueError("actual camera pixels differ: " + view)
        movie = stage / (view + ".mkv")
        probe = subprocess.run(["ffprobe", "-v", "error", "-count_frames", "-select_streams", "v:0",
                                "-show_entries", "stream=nb_read_frames,r_frame_rate", "-of", "json",
                                str(movie)], capture_output=True, text=True, check=True)
        stream = json.loads(probe.stdout)["streams"][0]
        if int(stream["nb_read_frames"]) != count or stream["r_frame_rate"] != "20/1":
            raise ValueError("original camera video frames differ: " + view)
        decoded = subprocess.run(["ffmpeg", "-v", "error", "-i", str(movie), "-f", "null", "-"],
                                 capture_output=True, text=True)
        if decoded.returncode:
            raise ValueError("original camera full decode failed: " + view)
    review = read(stage / "original-attempt/officer-review.json")
    if review.get("source_kind") != ("synthetic_review" if diagnostic_fixture else
                                     "original_independent_review"):
        raise ValueError("independent officer review missing")
    measured = measure(history, site, case, diagnostic_fixture=diagnostic_fixture)
    if (set(report.get("measurements", {})) != {"officer_exception_context", "officer_intersection_motion"}
            or report["measurements"]["officer_intersection_motion"]["value"]["motion"] != measured
            or report.get("legal_verdict_claimed") is not False
            or result.get("physical_acceptance_claimed") is not False):
        raise ValueError("saved officer measurement or acceptance claim differs")
    if not diagnostic_fixture and not (
            any(row["state"]["ego"]["across_or_within"] for row in history) and
            history[-1]["state"]["ego"]["across_or_within"] is False and
            history[-1]["state"]["ego"]["leading_station_m"] >
            site["intersection_entry_station_m"]):
        raise ValueError("original ego body traversal incomplete")
    return {"format": "c157964-selected-delivery-audit-v1", "case_id": case_id,
            "diagnostic_fixture": diagnostic_fixture, "source_frames": count,
            "capture_seal_sha256": sha(stage / "capture-seal.json"),
            "analysis_report_sha256": sha(stage / "analysis-report.json"),
            "checks": ["native_source", "all_participants", "time_join", "full_video_decode",
                       "actual_pixels", "physical_completion"],
            "physical_acceptance_claimed": False, "legal_judgment": "unresolved"}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage", type=Path, required=True)
    parser.add_argument("--case", required=True)
    parser.add_argument("--diagnostic-fixture", action="store_true")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = audit(args.stage, args.case, diagnostic_fixture=args.diagnostic_fixture)
    if args.output.exists():
        raise ValueError("refusing to replace delivery audit")
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(result["case_id"])
