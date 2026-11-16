"""Independent original-source comparison for ego speed increase before full pass."""
import argparse
import hashlib
import json
from pathlib import Path

from overtake_geometry import measure


def rows(value):
    return [json.loads(line) for line in value.splitlines() if line]


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def audit(reference_path, increased_path, *, rebound_overtaker=False):
    paths = [Path(reference_path), Path(increased_path)]
    specs = [json.loads(path.read_text()) for path in paths]
    files = [spec["files"] for spec in specs]
    receipts = [json.loads(f["overtake_source_receipt.json"]) for f in files]
    if not receipts[0]["case_id"].endswith("__observed_gives_way_holds_speed") or not receipts[1]["case_id"].endswith("__observed_gives_way_increases_speed_before_complete"):
        raise ValueError("Speed comparison exact case identity differs")
    fixed = ("overtake_site_original.json", "overview-frames.jsonl",
             "approach-frames.jsonl", "reference_corner-frames.jsonl",
             "driver_reference-frames.jsonl", "video_frames.jsonl")
    if any(files[0][name] != files[1][name] for name in fixed) or specs[0]["videos"] != specs[1]["videos"]:
        raise ValueError("Speed comparison fixed road or camera source differs")
    bodies = [rows(f["overtake_bodies_original.jsonl"]) for f in files]
    trace = [rows(f["trace.jsonl"]) for f in files]
    if rebound_overtaker:
        bodies[1][2]["overtaker"]["body_corners_xy_m"][0][0] += 0.25
        files[1]["overtake_bodies_original.jsonl"] = "".join(json.dumps(v, separators=(",", ":")) + "\n" for v in bodies[1])
        receipts[1]["source_sha256"]["overtake_bodies_original.jsonl"] = digest(files[1]["overtake_bodies_original.jsonl"])
    if len(bodies[0]) < 5 or len(bodies[0]) != len(bodies[1]):
        raise ValueError("Speed comparison original frame count differs")
    geometry = []
    for index in (0, 1):
        for name in ("overtake_bodies_original.jsonl", "trace.jsonl"):
            if digest(files[index][name]) != receipts[index]["source_sha256"][name]:
                raise ValueError("Speed comparison original source hash differs")
        geometry.append(measure(bodies[index], receipts[index]["ego_actor_id"], receipts[index]["overtaker_actor_id"]))
    for a, b, ta, tb in zip(bodies[0], bodies[1], trace[0], trace[1]):
        if (a["frame"] != b["frame"] or a["time_s"] != b["time_s"] or
                a["road_forward_xy"] != b["road_forward_xy"] or
                a["overtaker"] != b["overtaker"] or
                a["ego"]["id"] != b["ego"]["id"] or
                ta["frame"] != tb["frame"] or ta["time_s"] != tb["time_s"]):
            raise ValueError("Speed comparison fixed overtaker or frame source differs")
        ay = sum(p[1] for p in a["ego"]["body_corners_xy_m"]) / 4
        by = sum(p[1] for p in b["ego"]["body_corners_xy_m"]) / 4
        if abs(ay - by) > .01:
            raise ValueError("Speed comparison rightward path differs")
        for body, motion in ((a, ta), (b, tb)):
            center = [sum(p[axis] for p in body["ego"]["body_corners_xy_m"]) / 4 for axis in (0, 1)]
            if any(abs(center[axis] - motion["position"][name]) > .05 for axis, name in enumerate(("x", "y"))):
                raise ValueError("Speed comparison body/trace pose differs")
            if abs(body["ego"]["speed_mps"] - motion["speed_mps"]) > .01:
                raise ValueError("Speed comparison body/trace speed differs")
    first, second = geometry
    if first["first_complete_frame"] is None or second["first_complete_frame"] is None:
        raise ValueError("Speed comparison lacks a source-bracketed complete pass")
    if first["max_precompletion_speed_increase_mps"] > .01 or second["max_precompletion_speed_increase_mps"] < .9:
        raise ValueError("Speed comparison deliberate precompletion increase absent")
    first_change = next((row["frame"] for left, row in zip(trace[0], trace[1]) if row["speed_mps"] > left["speed_mps"] + .9), None)
    if first_change is None or first_change >= second["first_complete_frame"]:
        raise ValueError("Speed increase is not before full-body pass completion")
    return {"format": "worker-speed-before-comparison", "comparison_id": "speed_before_after_completion",
            "reference_case_id": receipts[0]["case_id"], "increased_case_id": receipts[1]["case_id"],
            "source_sha256": {str(path): hashlib.sha256(path.read_bytes()).hexdigest() for path in paths},
            "frames": len(bodies[0]), "first_speed_increase_frame": first_change,
            "first_complete_frame": second["first_complete_frame"],
            "precompletion_speed_increase_mps": second["max_precompletion_speed_increase_mps"],
            "physical_acceptance_claimed": False, "subjective_notice_confirmed": None,
            "legal_acceptance_claimed": False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("reference")
    parser.add_argument("increased")
    parser.add_argument("--output")
    parser.add_argument("--negative-rebound-overtaker", action="store_true")
    args = parser.parse_args()
    result = audit(args.reference, args.increased, rebound_overtaker=args.negative_rebound_overtaker)
    if args.output:
        Path(args.output).write_text(json.dumps(result, indent=2) + "\n")
    else:
        print(json.dumps(result))


if __name__ == "__main__":
    main()
