"""Prove the independent delivery audit on each exact synthetic source set."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
sys.path.insert(0, str(ROOT))
from delivery_audit import audit
from native_media import encode, sha
from saved_measurement import finalize_attempt

VIEWS = (("overview", 2, 2), ("approach", 2, 2),
         ("reference_corner", 2, 2), ("driver_reference", 2, 2))


def make_attempt(case: str, base: Path) -> Path:
    suffix = case.removeprefix(ROOT.name + "__")
    if suffix == case:
        raise ValueError("case does not belong to this assignment")
    diagnostic = ROOT / ("diagnostic.json" if suffix == "reference" else
                         "diagnostics/" + suffix + "/diagnostic.json")
    source = json.loads(diagnostic.read_text())
    if base.exists():
        shutil.rmtree(base)
    attempt = base / "attempt"
    attempt.mkdir(parents=True)
    for name, content in source["files"].items():
        target = attempt / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content)
    setup = json.loads((attempt / "authored-setup.json").read_text())
    if setup["case_id"] != case:
        raise ValueError("diagnostic source selects another exact case")
    trace_path, map_path = attempt / "trace.jsonl", attempt / "video_frames.jsonl"
    trace = [json.loads(line) for line in trace_path.read_text().splitlines()]
    mapping = [json.loads(line) for line in map_path.read_text().splitlines()]
    conditions = [json.loads(line) for line in
                  (attempt / "original-conditions.jsonl").read_text().splitlines()]
    if len(trace) != 900 or len(mapping) != 900 or len(conditions) != 900:
        raise ValueError("exact diagnostic source must contain 900 frames")
    gap = setup["variables"]["leader_initial_gap_m"]
    videos = {}
    for index, (name, width, height) in enumerate(VIEWS):
        pixels = bytes((0, 0, 0, 255, 25 + index, 0, 0, 255,
                        0, 25 + index, 0, 255, 0, 0, 25 + index, 255))
        digest = hashlib.sha256(pixels).hexdigest()
        raw = base / (name + ".bgra")
        raw.write_bytes(pixels)
        video = attempt / (name + ".mkv")
        encode([raw] * 900, width, height, video)
        videos[name] = sha(video)
        for frame, frame_map in zip(trace, mapping):
            frame["camera_sources"][name] = {
                "frame": frame["frame"], "time_s": frame["time_s"],
                "width": width, "height": height, "sha256": digest,
            }
            frame_map["camera_source_sha256"][name] = digest
    for row, condition in zip(trace, conditions):
        row["leader_position_m"] = [row["position_m"][0] + gap, 0, 0]
        if row["frame"] != condition["frame"] or row["time_s"] != condition["time_s"]:
            raise ValueError("source frame join differs")
    trace_path.write_text("".join(json.dumps(row) + "\n" for row in trace))
    map_path.write_text("".join(json.dumps(row) + "\n" for row in mapping))
    media_path = attempt / "media-receipt.json"
    media = json.loads(media_path.read_text())
    media.update(trace_sha256=sha(trace_path), frame_map_sha256=sha(map_path),
                 video_sha256=videos)
    media_path.write_text(json.dumps(media) + "\n")
    finalize_attempt(attempt, attempt / "analysis-report.json")
    return attempt


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("case")
    parser.add_argument("--negative", action="store_true")
    args = parser.parse_args()
    suffix = args.case.removeprefix(ROOT.name + "__")
    mode = "negative" if args.negative else "positive"
    base = REPO / ".runtime-work/c179789-delivery-audit" / suffix / mode
    attempt = make_attempt(args.case, base)
    if args.negative:
        status_path = attempt / "native-run-status.json"
        status = json.loads(status_path.read_text())
        status["restoration"]["restored"] = False
        status_path.write_text(json.dumps(status) + "\n")
        print(args.case, "negative restoration probe", flush=True)
        audit(attempt, diagnostic_test=True, diagnostic_views=VIEWS)
        raise AssertionError("negative restoration fixture passed unexpectedly")
    result = audit(attempt, diagnostic_test=True, diagnostic_views=VIEWS)
    if (result["case_id"] != args.case or result["frame_count"] != 900 or
            not all(result["checks"].values()) or
            result["participant_visibility_verified"] is not False or
            result["physical_acceptance_claimed"] is not False):
        raise ValueError("exact synthetic delivery audit proof incomplete")
    print(args.case, "independent synthetic source and decode audit passed")


if __name__ == "__main__":
    main()
