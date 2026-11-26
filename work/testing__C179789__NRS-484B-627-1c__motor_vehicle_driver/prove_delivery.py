"""Independently audit a diagnostic route attempt and reject stale site bytes."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
PRIVATE = Path(os.environ["SCENARIO_PIPELINE_OUTPUT_ROOT"]).resolve()
if not PRIVATE.is_relative_to(REPO / ".runtime-work"):
    raise ValueError("delivery fixture scratch must be under .runtime-work")
sys.path.insert(0, str(REPO / "runtime/scenario_pipeline"))
from worker_exchange.media import audit as audit_video


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audit(root: Path, case_id: str) -> dict:
    packet = json.loads((root / "original-route-motion.json").read_text())
    site = root / "original-site.json"
    if packet.get("case_id") != case_id or packet.get("site_sha256") != sha(site):
        raise ValueError("original route site hash differs")
    rows = packet["samples"]
    mapping = [json.loads(line) for line in (root / "video_frames.jsonl").read_text().splitlines()]
    if len(rows) != len(mapping) or any(row["original_frame"] != frame["carla_frame"] or
        row["time_s"] != frame["time_s"] or frame["video_frame"] != index
        for index, (row, frame) in enumerate(zip(rows, mapping))):
        raise ValueError("original route frame/time join differs")
    if len({(row["ego_id"], row["follower_id"]) for row in rows}) != 1:
        raise ValueError("original route participants differ")
    videos = {}
    for name in ("overview", "approach", "reference_corner", "driver_reference"):
        videos[name] = audit_video(root / (name + ".mkv"), len(rows),
                                   mapping_sha256=sha(root / "video_frames.jsonl"))
    result = json.loads((root / "result.json").read_text())
    if result.get("case_id") != case_id or result.get("physical_checks", {}).get("maneuver", {}).get("status") not in ("met", "not_met", "unverified"):
        raise ValueError("physical completion check missing")
    return {"case_id": case_id, "frame_count": len(rows), "full_video_decode": True,
            "all_participants": True, "time_join": True, "actual_pixels": True,
            "physical_completion_checked": True, "four_views": sorted(videos),
            "diagnostic_fixture": True, "physical_acceptance_claimed": False}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", required=True)
    parser.add_argument("--negative", action="store_true")
    args = parser.parse_args()
    tag = args.case.rsplit("__", 1)[-1]
    attempt = PRIVATE / ("saved-compat-" + tag + "-v1")
    if not attempt.is_dir():
        raise ValueError("exact saved diagnostic attempt missing")
    if args.negative:
        with tempfile.TemporaryDirectory(prefix="delivery-stale-", dir=PRIVATE) as temporary:
            stale = Path(temporary) / "attempt"
            shutil.copytree(attempt, stale)
            (stale / "original-site.json").write_text("{}\n")
            try:
                audit(stale, args.case)
            except ValueError as error:
                if "original route site hash differs" not in str(error):
                    raise
                print("original route site hash differs; rejected stale original source")
                raise SystemExit(2)
            raise AssertionError("stale route source accepted")
    print(json.dumps(audit(attempt, args.case), sort_keys=True))


if __name__ == "__main__":
    main()
