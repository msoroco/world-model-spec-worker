"""Independent CPU comparison of the two retained overtaking diagnostics."""

import argparse
import hashlib
import json
from pathlib import Path

from overtake_geometry import measure


def _hash(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _rows(value):
    return [json.loads(line) for line in value.splitlines() if line]


def audit(reference_path, no_yield_path):
    paths = [Path(reference_path), Path(no_yield_path)]
    values = [json.loads(path.read_text()) for path in paths]
    files = [value["files"] for value in values]
    identities = [json.loads(f["overtake_source_receipt.json"]) for f in files]
    if not identities[0]["case_id"].endswith("__observed_gives_way_holds_speed") or not identities[1]["case_id"].endswith("__observed_no_right_yield_holds_speed"):
        raise ValueError("Right-response comparison case identity differs")
    fixed = ("overtake_site_original.json", "overview-frames.jsonl",
             "approach-frames.jsonl", "reference_corner-frames.jsonl",
             "driver_reference-frames.jsonl", "video_frames.jsonl")
    if any(files[0][name] != files[1][name] for name in fixed) or values[0]["videos"] != values[1]["videos"]:
        raise ValueError("Right-response fixed road or camera source differs")
    bodies = [_rows(f["overtake_bodies_original.jsonl"]) for f in files]
    trace = [_rows(f["trace.jsonl"]) for f in files]
    if any(len(rows) < 3 for rows in bodies) or len(bodies[0]) != len(bodies[1]):
        raise ValueError("Right-response frame count differs")
    geometry = []
    for index in (0, 1):
        receipt = identities[index]
        for name in ("overtake_bodies_original.jsonl", "trace.jsonl"):
            if hashlib.sha256(files[index][name].encode()).hexdigest() != receipt["source_sha256"][name]:
                raise ValueError("Right-response original source hash differs")
        geometry.append(measure(bodies[index], receipt["ego_actor_id"], receipt["overtaker_actor_id"]))
    for row_pair, trace_pair in zip(zip(*bodies), zip(*trace)):
        before, after = row_pair
        left, right = trace_pair
        if (before["frame"] != after["frame"] or before["time_s"] != after["time_s"] or
                before["road_forward_xy"] != after["road_forward_xy"] or
                before["overtaker"] != after["overtaker"] or
                before["ego"]["id"] != after["ego"]["id"] or
                before["ego"]["speed_mps"] != after["ego"]["speed_mps"] or
                left["frame"] != right["frame"] or left["time_s"] != right["time_s"] or
                left["speed_mps"] != right["speed_mps"]):
            raise ValueError("Right-response fixed actor, speed or frame source differs")
        for body, motion in ((before, left), (after, right)):
            center = [sum(p[axis] for p in body["ego"]["body_corners_xy_m"]) / 4 for axis in (0, 1)]
            if any(abs(center[axis] - motion["position"][name]) > .05 for axis, name in enumerate(("x", "y"))):
                raise ValueError("Right-response body/trace pose differs")
        if abs(left["position"]["x"] - right["position"]["x"]) > .05:
            raise ValueError("Right-response longitudinal path changed beyond speed-preserving drift")
    first, second = geometry
    if (first["first_complete_frame"] != second["first_complete_frame"] or
            first["passing_side_at_first_frame"] != second["passing_side_at_first_frame"] or
            first["max_precompletion_speed_increase_mps"] != second["max_precompletion_speed_increase_mps"]):
        raise ValueError("Right-response fixed pass bracket or speed result differs")
    shift = first["max_precompletion_right_shift_m"] - second["max_precompletion_right_shift_m"]
    if not shift > .2:
        raise ValueError("Right-response deliberate lateral difference absent")
    return {"format": "worker-right-response-comparison", "comparison_id": "rightward_yield",
            "reference_case_id": identities[0]["case_id"], "no_yield_case_id": identities[1]["case_id"],
            "sources_sha256": {str(path): _hash(path) for path in paths},
            "frames": len(bodies[0]), "same_first_complete_frame": first["first_complete_frame"],
            "precompletion_right_shift_difference_m": shift,
            "physical_acceptance_claimed": False, "subjective_notice_confirmed": None,
            "legal_acceptance_claimed": False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("reference")
    parser.add_argument("no_yield")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    Path(args.output).write_text(json.dumps(audit(args.reference, args.no_yield), indent=2) + "\n")


if __name__ == "__main__":
    main()
