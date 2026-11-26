"""Independently test paired source isolation for the two cycle-pass contrasts."""

import argparse
import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
PAIRS = {"witness": ("witness_1", "witness_2"),
         "exception": ("exception_1_1", "exception_1_2"),
         "unsafe_available": ("exception_1_1", "exception_unsafe_available")}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def inspect(pair, negative=False):
    left_name, right_name = PAIRS[pair]
    paths = [REPO / ".runtime-work" / ("c247014-compat-" + name +
             ("-v6" if name == "exception_unsafe_available" else "-v4"))
             for name in (left_name, right_name)]
    for path in paths:
        if not path.is_dir():
            raise ValueError("Missing exact public source: " + str(path))
    l, r = [rows(path / "participant-poses.jsonl") for path in paths]
    lm, rm = [rows(path / "video_frames.jsonl") for path in paths]
    if negative:
        r[75]["cyclist"]["center_xy_m"][0] += 99
    if any(len(stream) != 600 for stream in (l, r, lm, rm)):
        raise ValueError("Controlled comparison missing 600 joined frames")
    for i, (a, b, av, bv) in enumerate(zip(l, r, lm, rm)):
        if (a["video_frame"] != b["video_frame"] or a["video_frame"] != i or
                av["video_frame"] != bv["video_frame"] or av["video_frame"] != i or
                a["time_s"] != b["time_s"] or av["time_s"] != bv["time_s"] or
                a["cyclist"] != b["cyclist"] or
                a["ego"]["center_xy_m"][0] != b["ego"]["center_xy_m"][0] or
                a["ego"]["speed_mps"] != b["ego"]["speed_mps"]):
            raise ValueError("Controlled non-target source differs at frame " + str(i))
    if pair == "witness":
        if any(a["left_blocker"] != b["left_blocker"] for a, b in zip(l, r)):
            raise ValueError("Witness pair changed left-lane occupant")
        changed = [i for i, (a, b) in enumerate(zip(l, r))
                   if a["ego"]["center_xy_m"][1] != b["ego"]["center_xy_m"][1]]
        if not changed or changed[0] >= 280:
            raise ValueError("Witness pair lacks planned early lane-move contrast")
        variable = "requested_lane_move"
    else:
        if any(a["ego"] != b["ego"] for a, b in zip(l, r)):
            raise ValueError("Exception pair changed subject motion")
        changed = [i for i, (a, b) in enumerate(zip(l, r)) if a["left_blocker"] != b["left_blocker"]]
        if not changed:
            raise ValueError("Exception pair lacks planned occupant contrast")
        if pair == "unsafe_available":
            decision = 180
            ego_x = r[decision]["ego"]["center_xy_m"][0]
            blocker_x = r[decision]["left_blocker"]["center_xy_m"][0]
            initial_gap = r[0]["ego"]["center_xy_m"][0] - r[0]["left_blocker"]["center_xy_m"][0]
            decision_gap = ego_x - blocker_x
            if not (0 < decision_gap < initial_gap):
                raise ValueError("Closing vehicle must remain behind at the lane-change decision")
        variable = ("closing_left_vehicle_context" if pair == "unsafe_available"
                    else "left_lane_occupant_plan")
    return {"format": "c247014-independent-comparison-audit-v1", "pair": pair,
            "cases": [HERE.name + "__" + left_name, HERE.name + "__" + right_name],
            "frames": 600, "source_sha256": {
                left_name: sha(paths[0] / "participant-poses.jsonl"),
                right_name: sha(paths[1] / "participant-poses.jsonl")},
            "deliberate_difference": variable, "changed_frames": len(changed),
            "closing_gap_m": {"initial": initial_gap, "lane_change_decision": decision_gap}
            if pair == "unsafe_available" else None,
            "synthetic_fixture": True, "original_native_observed": False,
            "legal_judgment": None}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--pair", choices=tuple(PAIRS), required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--negative", action="store_true")
    args = parser.parse_args()
    result = inspect(args.pair, args.negative)
    Path(args.output).write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"pair": args.pair, "changed_frames": result["changed_frames"]}))


if __name__ == "__main__":
    main()
