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
    if len(trace) != 900 or len(mapping) != 900:
        raise ValueError("Full saved frame history missing")
    if any(t["frame"] != m["carla_frame"] or abs(t["time_s"] - m["time_s"]) > 1e-6
           for t, m in zip(trace, mapping)):
        raise ValueError("Original trace/video time join differs")
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
