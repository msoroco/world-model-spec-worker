"""Thirty-second signed school-crossing entry requests and source meter."""
import argparse
import hashlib
import json
import math
from pathlib import Path


ASSIGNMENT = Path(__file__).resolve().parent.parent.name
CASES = {"entry_during_crossing": ASSIGNMENT + "__selected_1290826d__condition_a",
         "entry_after_crossing": ASSIGNMENT + "__selected_1290826d__condition_b"}
FRAMES = 600
RATE_HZ = 20
CROSSWALK_NEAR_X_M = 0.0
SIGN_X_M = -35.0
FRONT_OFFSET_M = 2.0


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines()]


def request_row(frame, condition):
    t = frame / RATE_HZ
    if condition == "entry_during_crossing":
        ego_x, speed = -50 + 4*t, 4.0
    elif t < 10:
        ego_x, speed = -50 + 4*t, 4.0
    elif t < 14:
        ego_x, speed = -10.0, 0.0
    else:
        ego_x, speed = -10 + 4*(t-14), 4.0
    pedestrian_in_crosswalk = 10 <= t < 14
    return {"case_id": CASES[condition], "condition": condition,
            "frame": frame, "time_s": t, "source_kind": "authored_native_request",
            "ego": {"center_x_m": round(ego_x, 6),
                    "front_x_m": round(ego_x+FRONT_OFFSET_M, 6),
                    "speed_mps": speed, "approach_side": "south"},
            "crosswalk": {"near_x_m": CROSSWALK_NEAR_X_M,
                          "width_m": 3.6576, "marked_yellow": True},
            "sign": {"legend": "School-Xing", "x_m": SIGN_X_M,
                     "displayed": True, "governs_crosswalk": True},
            "pedestrian": {"id": "crossing_person", "approach_side": "south",
                           "in_crosswalk": pedestrian_in_crosswalk,
                           "moving_toward_roadway": pedestrian_in_crosswalk},
            "original_native_observed": False, "legal_verdict": None}


def build(output):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    entries = []
    for condition in CASES:
        path = output/(condition+".jsonl")
        path.write_text("".join(json.dumps(request_row(i, condition), sort_keys=True)+"\n"
                                for i in range(FRAMES)))
        entries.append({"condition": condition, "case_id": CASES[condition],
                        "path": path.name, "sha256": sha(path), "frames": FRAMES})
    return {"format": "c394563-school-xing-request-v1", "entries": entries,
            "duration_s": 30.0, "rate_hz": RATE_HZ, "native_executed": False}


def meter(source):
    source = Path(source)
    data = rows(source)
    if len(data) != FRAMES:
        raise ValueError("Missing complete 600-frame source sequence")
    if len({r.get("case_id") for r in data}) != 1 or data[0]["case_id"] not in CASES.values():
        raise ValueError("Source case identity differs")
    if {r.get("source_kind") for r in data} not in (
            {"authored_native_request"}, {"synthetic_native_sample"}):
        raise ValueError("Unknown or unsealed source provenance")
    for i,row in enumerate(data):
        if row.get("frame") != i or abs(row.get("time_s",-1)-i/RATE_HZ)>1e-6:
            raise ValueError("Source frame/time join differs")
        xing, sign, ped, ego = (row.get(k,{}) for k in
                                ("crosswalk","sign","pedestrian","ego"))
        if (xing.get("near_x_m") != CROSSWALK_NEAR_X_M or
                xing.get("width_m") != 3.6576 or xing.get("marked_yellow") is not True):
            raise ValueError("Marked school crosswalk source absent")
        if (sign.get("legend") != "School-Xing" or sign.get("displayed") is not True or
                sign.get("governs_crosswalk") is not True or
                sign.get("x_m") > -30.48):
            raise ValueError("Displayed advance School-Xing sign source absent")
        if ped.get("id") != "crossing_person" or ped.get("approach_side") != "south":
            raise ValueError("Same-side pedestrian source absent")
        values = [ego.get("center_x_m"),ego.get("front_x_m"),ego.get("speed_mps")]
        if any(not isinstance(v,(int,float)) or not math.isfinite(v) for v in values):
            raise ValueError("Nonfinite or absent ego readback")
        if ego.get("approach_side") != "south" or abs(
                ego["front_x_m"]-ego["center_x_m"]-FRONT_OFFSET_M)>1e-4:
            raise ValueError("Ego approach/body source differs")
    crossing = next((r for r in data if r["ego"]["front_x_m"] >= CROSSWALK_NEAR_X_M),None)
    if crossing is None:
        raise ValueError("No vehicle crosswalk entry in source window")
    ped = crossing["pedestrian"]
    return {"format":"c394563-school-xing-entry-meter-v1",
            "case_id":data[0]["case_id"],"source_sha256":sha(source),
            "source_kind":data[0]["source_kind"],"frames":FRAMES,"duration_s":30,
            "vehicle_entry_frame":crossing["frame"],
            "same_side_person_in_crosswalk_at_entry":ped["in_crosswalk"],
            "person_moving_toward_roadway_at_entry":ped["moving_toward_roadway"],
            "pedestrian_intention_claimed":False,"physical_completion_claimed":False,
            "legal_verdict_claimed":False}


def prove(output):
    manifest = build(output)
    output = Path(output)
    meters = {e["condition"]:meter(output/e["path"]) for e in manifest["entries"]}
    if not meters["entry_during_crossing"]["same_side_person_in_crosswalk_at_entry"]:
        raise AssertionError("Entry diagnostic lacks same-side crossing person")
    if meters["entry_after_crossing"]["same_side_person_in_crosswalk_at_entry"]:
        raise AssertionError("Delayed entry overlaps crossing person")
    negatives = {}
    for label,mutate,expected in (
        ("missing_sign",lambda r:r[0]["sign"].clear(),
         "Displayed advance School-Xing sign source absent"),
        ("missing_crosswalk",lambda r:r[0]["crosswalk"].clear(),
         "Marked school crosswalk source absent"),
        ("missing_person",lambda r:r[0]["pedestrian"].clear(),
         "Same-side pedestrian source absent"),
        ("forged_original",lambda r:r[0].update(source_kind="original_native"),
         "Unknown or unsealed source provenance")):
        changed=rows(output/"entry_during_crossing.jsonl")
        mutate(changed)
        path=output/(label+".jsonl")
        path.write_text("".join(json.dumps(row,sort_keys=True)+"\n" for row in changed))
        try:meter(path)
        except ValueError as exc:
            if str(exc)!=expected:raise
            negatives[label]=expected
        else:raise AssertionError("Missing/forged source accepted: "+label)
    return {"format":"c394563-school-xing-diagnostic-proof-v1",
            "manifest":manifest,"meters":meters,"negative_rejections":negatives,
            "native_executed":False,"legal_verdict_claimed":False}


if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("command",choices=("build","meter","prove"))
    parser.add_argument("--output");parser.add_argument("--source")
    args=parser.parse_args()
    result=(meter(args.source) if args.command=="meter" else
            build(args.output) if args.command=="build" else prove(args.output))
    print(json.dumps(result,indent=2,sort_keys=True))
