"""Independently audit retained source frames and saved-only camera decode."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess

from capture_seal import CAMERAS, seal
from flagger_zone import CASES, measure_original
from source_packet import ASSIGNMENT


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _decode(video: Path, frame_count: int, dimensions: list[int]) -> None:
    probe = subprocess.run(["ffprobe", "-v", "error", "-count_frames", "-select_streams",
                            "v:0", "-show_entries", "stream=width,height,nb_read_frames,r_frame_rate",
                            "-of", "json", str(video)], capture_output=True, text=True, check=True)
    stream = json.loads(probe.stdout)["streams"][0]
    if ([stream["width"], stream["height"]] != dimensions or
            stream["r_frame_rate"] != "20/1" or
            int(stream["nb_read_frames"]) != frame_count):
        raise ValueError("saved video metadata differs: " + video.name)
    decoded = subprocess.run(["ffmpeg", "-v", "error", "-i", str(video),
                              "-f", "null", "-"], capture_output=True, text=True)
    if decoded.returncode:
        raise ValueError("saved video full decode failed: " + video.name)


def audit(stage: Path, saved: Path, *, case_id: str, diagnostic_fixture: bool = False) -> dict:
    stage, saved = Path(stage), Path(saved)
    if case_id not in {ASSIGNMENT + "__" + case.name for case in CASES}:
        raise ValueError("delivery case outside exact assignment")
    sealed = seal(stage, diagnostic_fixture=diagnostic_fixture)
    if sealed["case_id"] != case_id:
        raise ValueError("delivery case differs from original source")
    report_path = saved / "saved-report.json"
    report = json.loads(report_path.read_text())
    if (report.get("case_id") != case_id or report.get("source_kind") != sealed["source_kind"] or
            report.get("capture_seal") != sealed or
            report.get("physical_acceptance_claimed") is not False or
            report.get("legal_acceptance_claimed") is not False):
        raise ValueError("saved report source or acceptance status differs")
    for name, digest in report["retained_source_sha256"].items():
        if not (stage / name).is_file() or sha(stage / name) != digest:
            raise ValueError("retained original source changed: " + name)
    if set(report["videos"]) != set(CAMERAS):
        raise ValueError("four saved videos required")
    for name in CAMERAS:
        item = report["videos"][name]
        video = saved / (name + ".mkv")
        if (item.get("path") != video.name or sha(video) != item.get("sha256") or
                item.get("decoded_frames") != sealed["source_frame_count"]):
            raise ValueError("saved camera hash or frame count differs: " + name)
        _decode(video, sealed["source_frame_count"], sealed["camera_sources"][name]["dimensions"])
    physical = None
    if not diagnostic_fixture:
        packet = json.loads((stage / "source-packet.json").read_text())
        rows = [json.loads(line) for line in (stage / "original-ticks.jsonl").read_text().splitlines()]
        case = next(case for case in CASES if case_id.endswith("__" + case.name))
        physical = measure_original(rows, packet["scene"], case)
    return {"format": "c230235-independent-delivery-audit-v1",
            "case_id": case_id, "source_kind": sealed["source_kind"],
            "capture_seal_sha256": hashlib.sha256(json.dumps(sealed, sort_keys=True).encode()).hexdigest(),
            "saved_report_sha256": sha(report_path),
            "source_frames": sealed["source_frame_count"],
            "checks": ["source_packet", "all_participants", "time_join",
                       "four_camera_full_decode", "actual_pixels", "owner_release"],
            "physical_measurement": physical,
            "physical_acceptance_claimed": False,
            "legal_acceptance_claimed": False}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage", required=True, type=Path)
    parser.add_argument("--saved", required=True, type=Path)
    parser.add_argument("--case", required=True)
    parser.add_argument("--diagnostic-fixture", action="store_true")
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("delivery audit output already exists")
    receipt = audit(args.stage, args.saved, case_id=args.case,
                    diagnostic_fixture=args.diagnostic_fixture)
    args.output.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(receipt["case_id"])
