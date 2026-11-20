"""Independent source-trace comparison for the C178244 left-turn cases.

This is a CPU audit of retained acquisition sources. Diagnostic inputs establish
only that the comparison procedure works; they do not establish legal district
classification, Native motion, lamp pixels, or physical acceptance.
"""

import argparse
import hashlib
import json
import math
from pathlib import Path


GROUPS = {
    "business_threshold_100_ft": ("left_business_under_100_ft", "left_business_at_100_ft", "left_business_over_100_ft"),
    "other_threshold_300_ft": ("left_other_under_300_ft", "left_other_at_300_ft", "left_other_over_300_ft"),
    "business_signal_interruption": ("left_business_at_100_ft", "left_interrupted"),
}


def require(ok, message):
    if not ok:
        raise ValueError(message)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def load(root):
    root = Path(root)
    files = ("road.xodr", "drive_history.jsonl", "body_history.jsonl", "route_context.json",
             "district-site-packet.json", "district-site-source.txt", "capture/native/frames.jsonl")
    hashes = {name: sha(root / name) for name in files}
    drive, body, frames = (rows(root / name) for name in
                           ("drive_history.jsonl", "body_history.jsonl", "capture/native/frames.jsonl"))
    context = json.loads((root / "route_context.json").read_text())
    packet = json.loads((root / "district-site-packet.json").read_text())
    require(len(drive) >= 3 and len(drive) == len(body) == len(frames), "Source frame counts differ")
    require([r["frame"] for r in drive] == [r["frame"] for r in body] ==
            [r["frame"] for r in frames], "Original frame join changed")
    require([r["time_s"] for r in drive] == [r["time_s"] for r in body] ==
            [r["simulation_time"] for r in frames], "Original time join changed")
    require(all(drive[i]["time_s"] > drive[i - 1]["time_s"] for i in range(1, len(drive))),
            "Original time is not increasing")
    require(context["district_review_verified"] is True and packet["independent_review"] is True,
            "District source is not marked reviewed")
    require(context["district_type"] == packet["district_type"] and
            context["district_source_sha256"] == packet["source_document_sha256"] ==
            hashes["district-site-source.txt"], "District source binding changed")
    require(packet["authored_map_sha256"] == hashes["road.xodr"], "District map binding changed")
    require(context["approach_road_id"] != context["outgoing_road_id"], "No turn route")
    require(context["turn_onset_frame"] == drive[-1]["frame"], "Turn onset differs from source")
    require(all(type(r["left_indicator"]) is bool and type(r["ego_light_mask"]) is int and
                r["left_indicator"] == bool(r["ego_light_mask"] & 32) for r in drive),
            "Left indicator differs from original light mask")
    require(drive[-1]["ego_heading_deg"] > drive[0]["ego_heading_deg"] + 10,
            "Measured route is not a left turn")
    path = 0.0
    onset_path = None
    start_frame = None
    off_frames = []
    for i, row in enumerate(drive):
        if i:
            path += math.dist(drive[i - 1]["ego_position_xy_m"], row["ego_position_xy_m"])
        if not row["left_indicator"]:
            off_frames.append(row["frame"])
            onset_path = None
        elif i and not drive[i - 1]["left_indicator"]:
            onset_path = path
            start_frame = row["frame"]
    require(onset_path is not None and off_frames, "Continuous signal start is not observed")
    distance = path - onset_path
    return {"root": str(root), "hashes": hashes, "drive": drive, "context": context,
            "distance_m": distance, "start_frame": start_frame, "off_frames": off_frames}


def audit(comparison_id, sources):
    names = GROUPS.get(comparison_id)
    require(names is not None, "Unknown comparison ID")
    require(set(sources) == set(names) and len(sources) == len(names), "Comparison source cases differ from plan")
    evidence = {name: load(sources[name]) for name in names}
    first = evidence[names[0]]
    for name in names[1:]:
        item = evidence[name]
        require(item["hashes"]["road.xodr"] == first["hashes"]["road.xodr"], "Fixed road map changed")
        require(item["hashes"]["district-site-source.txt"] ==
                first["hashes"]["district-site-source.txt"], "Fixed district source changed")
        for key in ("approach_road_id", "outgoing_road_id", "approach_lane_id", "outgoing_lane_id",
                    "district_type", "turn_onset_frame"):
            require(item["context"][key] == first["context"][key], "Fixed route context changed: " + key)
    if comparison_id == "business_threshold_100_ft":
        under, at, over = (evidence[name] for name in names)
        require(first["context"]["district_type"] == "business", "Business context missing")
        require(under["hashes"]["body_history.jsonl"] == at["hashes"]["body_history.jsonl"],
                "Below/at fixed body motion changed")
        require(under["distance_m"] < 30.48 and math.isclose(at["distance_m"], 30.48, abs_tol=1e-6)
                and over["distance_m"] > 30.48, "100-foot contrast missing")
    elif comparison_id == "other_threshold_300_ft":
        under, at, over = (evidence[name] for name in names)
        require(first["context"]["district_type"] == "other", "Other-area context missing")
        require(under["hashes"]["body_history.jsonl"] == at["hashes"]["body_history.jsonl"],
                "Below/at fixed body motion changed")
        require(under["distance_m"] < 91.44 and math.isclose(at["distance_m"], 91.44, abs_tol=1e-6)
                and over["distance_m"] > 91.44,
                "300-foot contrast missing")
    else:
        continuous, interrupted = (evidence[name] for name in names)
        require(first["context"]["district_type"] == "business", "Business context missing")
        require(continuous["hashes"]["body_history.jsonl"] ==
                interrupted["hashes"]["body_history.jsonl"], "Fixed body motion changed")
        require(math.isclose(continuous["distance_m"], 30.48, abs_tol=1e-6) and
                interrupted["distance_m"] < 30.48 and
                any(frame > interrupted["off_frames"][0] for frame in interrupted["off_frames"][1:]),
                "Continuous/interrupted contrast missing")
    return {"format": "worker-left-signal-source-comparison", "comparison_id": comparison_id,
            "source_scope": "retained acquisition sources", "software_comparison_passed": True,
            "physical_acceptance_claimed": False, "legal_acceptance_claimed": False,
            "cases": {name: {"source_root": item["root"], "source_hashes": item["hashes"],
                              "continuous_left_signal_distance_m": item["distance_m"],
                              "last_signal_start_frame": item["start_frame"]}
                      for name, item in evidence.items()}}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--comparison-id", choices=GROUPS, required=True)
    parser.add_argument("--source", action="append", nargs=2, metavar=("CASE_SUFFIX", "ATTEMPT"), required=True)
    args = parser.parse_args()
    sources = dict(args.source)
    require(len(sources) == len(args.source), "Duplicate comparison source")
    print(json.dumps(audit(args.comparison_id, sources), indent=2))


if __name__ == "__main__":
    main()
