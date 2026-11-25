"""Independent CPU preflight for a selected saved delivery, without acceptance."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from delivery_audit import DeliveryError, audit_saved


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rows(path: Path):
    return [json.loads(line) for line in path.read_text().splitlines() if line]


def join_original_frames(events, trace, mapping):
    if not all(len(items) == 900 for items in (events, trace, mapping)):
        raise ValueError("Full saved frame history missing")
    for index, (event, tick, frame) in enumerate(zip(events, trace, mapping)):
        original_frame = event.get("frame")
        original_time = event.get("time_s")
        if (type(original_frame) is not int or type(original_time) not in (int, float) or
                type(frame.get("video_frame")) is not int or
                frame["video_frame"] != index or
                original_frame != tick.get("frame") or
                original_frame != frame.get("carla_frame") or
                any(type(item) not in (int, float) for item in
                    (tick.get("time_s"), frame.get("time_s"))) or
                abs(original_time - tick["time_s"]) > 1e-6 or
                abs(original_time - frame["time_s"]) > 1e-6):
            raise ValueError("Sealed original event/trace/video frame join differs at " + str(index))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", required=True)
    parser.add_argument("--attempt", required=True)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--negative-missing-source", action="store_true")
    args = parser.parse_args()
    attempt = Path(args.attempt).resolve()
    manifest = json.loads(Path(args.manifest).read_text())
    entry = next(item for item in manifest["cases"] if item["case_id"] == args.case)
    saved = json.loads((attempt / "saved-manifest.json").read_text())
    if saved["case_id"] != args.case:
        raise ValueError("Saved attempt selects another exact case")
    if args.negative_missing_source:
        saved["sources"]["original_events"] = {"path": "missing-original-events.json",
                                               "sha256": "0" * 64}
        try:
            audit_saved(attempt, saved)
        except DeliveryError as error:
            print("sealed original missing or changed: " + str(error))
            return 1
        raise AssertionError("Missing original source was accepted")
    audited = audit_saved(attempt, saved)
    events = json.loads((attempt / saved["sources"]["original_events"]["path"]).read_text())
    if any(not isinstance(event.get("other_users"), list) or
           any(user.get("source_kind") != "native_world_snapshot" for user in event["other_users"])
           for event in events):
        raise ValueError("Original participant inventory incomplete")
    trace = rows(attempt / "trace.jsonl")
    mapping = rows(attempt / "video_frames.jsonl")
    join_original_frames(events, trace, mapping)
    for name, view in saved["camera_views"].items():
        video = attempt / view["source"]["path"]
        result = subprocess.run(["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error",
                                 "-xerror", "-i", str(video), "-map", "0:v:0", "-f", "null", "-"],
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        if result.returncode:
            raise ValueError("Four-view pixel stream cannot be decoded: " + name + ": " + result.stdout[-500:])
    physical = entry["physical_preparation"]
    receipt = HERE / physical["receipt"]
    if sha(receipt) != physical["sha256"]:
        raise ValueError("Physical completion preparation receipt changed")
    probe = json.loads(receipt.read_text())
    kinds = {item["kind"] for item in probe["fixtures"]}
    if probe["case_id"] != args.case or kinds != {"complete_motion", "incomplete_motion", "missing_evidence"}:
        raise ValueError("Physical completion evaluator lacks three-valued CPU proof")
    print(json.dumps({"case_id": args.case, "prepared": True,
                      "original_frames": audited["original_frames"],
                      "joined_frames": len(trace), "decoded_views": 4,
                      "physical_outcomes_tested": sorted(kinds),
                      "physical_acceptance_claimed": False,
                      "legal_acceptance_claimed": False}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
