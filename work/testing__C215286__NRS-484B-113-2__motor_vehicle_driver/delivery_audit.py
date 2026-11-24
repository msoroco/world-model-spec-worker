"""Independent source, timestamp, geometry and decoded-pixel delivery audit."""

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path

from analyze_source import load_measured
from crosswalk_delivery import audit as audit_relation

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
VIEWS = ("overview", "approach", "reference_corner", "driver_reference")
TARGETS = {"reverse_clear": "disjoint", "reverse_tangent": "contact",
           "reverse_overlap": "overlap"}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line]


def audit(attempt, case_id):
    from worker_exchange.media import audit as decode, check_four_view_sources

    root = Path(attempt).resolve()
    key = case_id.split("__")[-1]
    if key not in TARGETS or not (root / "construction.json").is_file():
        raise ValueError("exact selected case and construction required")
    construction = json.loads((root / "construction.json").read_text())
    if construction["case_id"] != case_id:
        raise ValueError("selected construction identity differs")
    source, measured, frame_hash = load_measured(root)
    if source["map_packet"]["case_id"] != case_id:
        raise ValueError("reviewed site packet case differs")
    relation = audit_relation(measured, expected_relation=TARGETS[key])
    result = json.loads((root / "result.json").read_text())
    if result["case_id"] != case_id or result.get("physical_acceptance_claimed") is True:
        raise ValueError("selected result identity or acceptance differs")
    trace = rows(root / result["trace_reference"])
    mapping = rows(root / result["video_frame_map_reference"])
    if not trace or len(trace) != len(mapping) or len(trace) != relation["frame_count"]:
        raise ValueError("original source/trace/video frame counts differ")
    for index, (point, frame, geometry) in enumerate(zip(trace, mapping, measured["frames"])):
        if (frame.get("video_frame") != index or
                point["frame"] != frame["carla_frame"] or
                abs(point["time_s"] - frame["time_s"]) > 1e-6 or
                abs(geometry["time_s"] - frame["time_s"]) > 1e-6):
            raise ValueError("original timestamp/frame join differs")
    views = {name: root / (name + ".mkv") for name in VIEWS}
    check_four_view_sources(views)
    map_hash = sha(root / "video_frames.jsonl")
    decoded = {name: decode(path, len(mapping), mapping_sha256=map_hash)
               for name, path in views.items()}
    primary = decode(root / "raw.mkv", len(mapping), mapping_sha256=map_hash)
    provenance = json.loads((root / "acquisition-provenance.json").read_text()) if (
        root / "acquisition-provenance.json").is_file() else {}
    diagnostic = provenance.get("diagnostic_fixture") is True or (
        root / "fixture-provenance.json").is_file()
    if not diagnostic:
        for frame in mapping:
            sources = frame.get("camera_sources")
            if not isinstance(sources, dict) or set(sources) != set(VIEWS):
                raise ValueError("Native original camera sources missing")
            for view, item in sources.items():
                path = root / "capture" / item["path"]
                if not path.is_file() or sha(path) != item["sha256"]:
                    raise ValueError("Native original camera pixel source differs")
    return {"format": "c215286-independent-delivery-audit", "case_id": case_id,
            "passed": True, "diagnostic_fixture": diagnostic,
            "physical_acceptance_claimed": False, "legal_acceptance_claimed": False,
            "source_frame_sha256": frame_hash, "frame_map_sha256": map_hash,
            "original_frames": len(mapping), "relation": relation,
            "source_decodes": {name: {"frames": value["frames"],
                                       "rgb_sequence_sha256": value["rgb_sequence_sha256"]}
                               for name, value in decoded.items()},
            "primary_decode": {"frames": primary["frames"],
                               "rgb_sequence_sha256": primary["rgb_sequence_sha256"]}}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", required=True)
    parser.add_argument("--case", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--negative-missing-source", action="store_true")
    args = parser.parse_args()
    os.environ.setdefault("SCENARIO_PIPELINE_OUTPUT_ROOT",
                          str(REPO / ".runtime-work" / "c215286-audit-runtime"))
    if args.negative_missing_source:
        missing = Path(args.attempt) / "reverse-body-crosswalk-source.jsonl"
        if missing.exists():
            raise ValueError("negative fixture still contains required original source")
    result = audit(args.attempt, args.case)
    Path(args.output).write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"case_id": args.case, "passed": True,
                      "diagnostic_fixture": result["diagnostic_fixture"]}))


if __name__ == "__main__":
    main()
