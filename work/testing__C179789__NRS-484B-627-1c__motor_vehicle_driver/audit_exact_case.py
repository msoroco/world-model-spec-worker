"""Independent source audit for one original C179789 Native route attempt."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
if not Path(os.environ.get("SCENARIO_PIPELINE_OUTPUT_ROOT", "/")).resolve().is_relative_to(REPO / ".runtime-work"):
    raise RuntimeError("Set SCENARIO_PIPELINE_OUTPUT_ROOT under .runtime-work")
sys.path.insert(0, str(REPO / "runtime/scenario_pipeline"))
from worker_exchange.media import audit as audit_video


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audit(root: Path, case_id: str) -> dict:
    source = json.loads((root / "original-route-motion.json").read_text())
    site = root / "original-site.json"
    if source.get("source_kind") != "original_native" or source.get("case_id") != case_id or \
            source.get("site_sha256") != sha(site) or len(source.get("samples", [])) != 900:
        raise ValueError("original exact route source or 900-frame sample missing")
    declaration = json.loads((root / "acquisition.json").read_text())
    for name in ("original-site.json", "original-route-motion.json", "trace.jsonl",
                 "video_frames.jsonl", "body_history.jsonl", "road.xodr",
                 "carla_recorder.log", "overview.mkv", "approach.mkv",
                 "reference_corner.mkv", "driver_reference.mkv"):
        if declaration.get(name, {}).get("kind") != "original_native" or \
                declaration[name].get("sha256") != sha(root / name):
            raise ValueError("original route source hash differs: " + name)
    site_data = json.loads(site.read_text())
    if not site_data.get("reviewed_original_site") or site_data.get("diagnostic_fixture") is True:
        raise ValueError("reviewed original route authority missing")
    map_ref = site_data["map_ref"]
    if sha(root / "road.xodr") != map_ref["sha256"]:
        raise ValueError("original Native map differs from reviewed source")
    rows = source["samples"]
    mapping = [json.loads(line) for line in (root / "video_frames.jsonl").read_text().splitlines()]
    if len(mapping) != 900 or any(row["original_frame"] != frame["carla_frame"] or
            row["time_s"] != frame["time_s"] or frame["video_frame"] != index
            for index, (row, frame) in enumerate(zip(rows, mapping))):
        raise ValueError("original route motion and four-view time join differs")
    views = {}
    for name in ("overview", "approach", "reference_corner", "driver_reference"):
        views[name] = audit_video(root / (name + ".mkv"), 900,
                                  mapping_sha256=sha(root / "video_frames.jsonl"))
    return {"format": "c179789-original-route-source-audit", "case_id": case_id,
            "original_frame_count": 900, "four_video_sources": sorted(views),
            "source_sha256": {name: value["sha256"] for name, value in declaration.items()},
            "source_decode_passed": True, "physical_acceptance_claimed": False,
            "legal_judgment": None}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", required=True)
    parser.add_argument("--attempt", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("fresh route source audit output required")
    args.output.write_text(json.dumps(audit(args.attempt, args.case), indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
