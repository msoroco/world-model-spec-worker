"""Independent three-case original-source audit for speed timing around complete passing."""
import argparse
import hashlib
import json
from pathlib import Path

from audit_speed_before import audit as audit_before, rows
from overtake_geometry import measure


def sha(value):
    return hashlib.sha256(value.encode()).hexdigest()


def audit(reference_path, before_path, after_path, *, negative_early_after=False):
    before = audit_before(reference_path, before_path)
    paths = [Path(reference_path), Path(after_path)]
    specs = [json.loads(p.read_text()) for p in paths]
    files = [s["files"] for s in specs]
    receipts = [json.loads(f["overtake_source_receipt.json"]) for f in files]
    if not receipts[1]["case_id"].endswith("__observed_gives_way_increases_speed_after_complete"):
        raise ValueError("After-case exact identity differs")
    fixed = ("overtake_site_original.json", "overview-frames.jsonl", "approach-frames.jsonl",
             "reference_corner-frames.jsonl", "driver_reference-frames.jsonl", "video_frames.jsonl")
    if any(files[0][name] != files[1][name] for name in fixed) or specs[0]["videos"] != specs[1]["videos"]:
        raise ValueError("After-case fixed road or camera source differs")
    bodies = [rows(f["overtake_bodies_original.jsonl"]) for f in files]
    traces = [rows(f["trace.jsonl"]) for f in files]
    if negative_early_after:
        bodies[1][3]["ego"]["speed_mps"] += 1.
        traces[1][3]["speed_mps"] += 1.
        files[1]["overtake_bodies_original.jsonl"] = "".join(json.dumps(v,separators=(",",":"))+"\n" for v in bodies[1])
        files[1]["trace.jsonl"] = "".join(json.dumps(v,separators=(",",":"))+"\n" for v in traces[1])
        for name in ("overtake_bodies_original.jsonl", "trace.jsonl"):
            receipts[1]["source_sha256"][name] = sha(files[1][name])
    if len(bodies[0]) != len(bodies[1]) or len(traces[0]) != len(traces[1]):
        raise ValueError("After-case original frame count differs")
    geometries = []
    for i in (0,1):
        for name in ("overtake_bodies_original.jsonl", "trace.jsonl"):
            if sha(files[i][name]) != receipts[i]["source_sha256"][name]:
                raise ValueError("After-case source hash differs")
        geometries.append(measure(bodies[i], receipts[i]["ego_actor_id"], receipts[i]["overtaker_actor_id"]))
    first, second = geometries
    if first["first_complete_frame"] is None or first["first_complete_frame"] != second["first_complete_frame"]:
        raise ValueError("After-case first complete-pass bracket differs")
    if first["max_precompletion_speed_increase_mps"] > .01 or second["max_precompletion_speed_increase_mps"] > .01:
        raise ValueError("After-case precompletion speed changed")
    after_increase = None
    for original, changed, left, right in zip(bodies[0], bodies[1], traces[0], traces[1]):
        if (original["frame"] != changed["frame"] or original["time_s"] != changed["time_s"] or
                original["overtaker"] != changed["overtaker"] or
                original["road_forward_xy"] != changed["road_forward_xy"] or
                left["frame"] != right["frame"] or left["time_s"] != right["time_s"]):
            raise ValueError("After-case fixed overtaker or frame source differs")
        for a,b in zip(original["ego"]["body_corners_xy_m"],changed["ego"]["body_corners_xy_m"]):
            if abs(a[1]-b[1]) > .01:
                raise ValueError("After-case rightward path differs")
        if abs(changed["ego"]["speed_mps"] - right["speed_mps"]) > .01:
            raise ValueError("After-case body/trace speed differs")
        if right["speed_mps"] > left["speed_mps"] + .9 and after_increase is None:
            after_increase = right["frame"]
        if right["frame"] <= second["first_complete_frame"] and abs(right["speed_mps"]-left["speed_mps"]) > .01:
            raise ValueError("After-case speed changed before full-body completion")
    if after_increase is None or after_increase <= second["first_complete_frame"]:
        raise ValueError("After-case deliberate later speed increase absent")
    if before["first_speed_increase_frame"] >= before["first_complete_frame"]:
        raise ValueError("Before-case timing proof changed")
    return {"format":"worker-speed-timing-comparison","comparison_id":"speed_before_after_completion",
            "reference_case_id":receipts[0]["case_id"],"before_case_id":before["increased_case_id"],
            "after_case_id":receipts[1]["case_id"],"sources_sha256":{str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in [Path(reference_path),Path(before_path),Path(after_path)]},
            "before_speed_increase_frame":before["first_speed_increase_frame"],
            "before_first_complete_frame":before["first_complete_frame"],
            "after_first_complete_frame":second["first_complete_frame"],
            "after_speed_increase_frame":after_increase,
            "physical_acceptance_claimed":False,"subjective_notice_confirmed":None,"legal_acceptance_claimed":False}


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("reference")
    parser.add_argument("before")
    parser.add_argument("after")
    parser.add_argument("--output")
    parser.add_argument("--negative-early-after",action="store_true")
    args=parser.parse_args()
    result=audit(args.reference,args.before,args.after,negative_early_after=args.negative_early_after)
    if args.output:Path(args.output).write_text(json.dumps(result,indent=2)+"\n")
    else:print(json.dumps(result))

if __name__=="__main__":main()
