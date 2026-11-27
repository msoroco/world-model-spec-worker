"""Independent exact-pair audit of held context and measured first stop position."""

import argparse
import copy
import hashlib
import json
from pathlib import Path

from yield_crosswalk_scene import request

HERE = Path(__file__).resolve().parent
AID = HERE.name
SUFFIXES = ("before_crosswalk", "past_crosswalk")
GROUP = AID + "__comparison"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def rows(path):
    value = [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]
    if len(value) != 600:
        raise ValueError("Comparison lacks full 600-frame source")
    return value


def verify_requests():
    a, b = [request(slug) for slug in SUFFIXES]
    changed = {key for key in set(a) | set(b) if a.get(key) != b.get(key)}
    if changed != {"case", "controller"}:
        raise ValueError("Uncontrolled authored crosswalk comparison: " + str(changed))
    if (a["controller"]["policy"] != b["controller"]["policy"] or
            a["controller"]["requested_stop_front_x_m"] != -9 or
            b["controller"]["requested_stop_front_x_m"] != -4 or
            a["road_opendrive"] != b["road_opendrive"] or a["cameras"] != b["cameras"]):
        raise ValueError("Yield sign, road, cameras or stop-position contrast differs")


def verify_rows(first, second):
    if len(first) != 600 or len(second) != 600:
        raise ValueError("Comparison requires full source histories")
    for i, (a, b) in enumerate(zip(first, second)):
        if (a.get("video_frame") != i or b.get("video_frame") != i or
                a.get("native_frame") != b.get("native_frame") or
                abs(a.get("time_s", -1) - b.get("time_s", -2)) > 1e-6 or
                a.get("intersecting_vehicle_y_m") != b.get("intersecting_vehicle_y_m") or
                a.get("intersecting_speed_mps") != b.get("intersecting_speed_mps") or
                a.get("source_cameras") != b.get("source_cameras")):
            raise ValueError("Fixed traffic, clock or camera source changed")
    return True


def first_rest(rows_):
    for row in rows_:
        if row["ego_speed_mps"] <= .1:
            return row["ego_x_m"] + row["ego_length_m"] / 2
    raise ValueError("No recorded stop in comparison")


def verify_contrast(first, second):
    a, b = first_rest(first), first_rest(second)
    if not a < -6 <= b <= -4:
        raise ValueError("Before-versus-within-crosswalk first-rest contrast absent")
    return {"before_front_x_m": a, "past_front_x_m": b,
            "near_side_crosswalk_x_m": -6, "safety_stop_required": "unassessed",
            "legal_compliance": "unassessed"}


def audit(folders, output):
    if len(folders) != 2:
        raise ValueError("Exact comparison membership differs")
    verify_requests()
    histories = []
    hashes = []
    for slug, folder in zip(SUFFIXES, map(Path, folders)):
        result_path = folder / "result.json"
        result = read(result_path)
        if (result.get("case_id") != AID + "__" + slug or
                result.get("provenance_kind") != "native" or
                result.get("diagnostic_fixture") is not False or
                result.get("physical_checks", {}).get("maneuver", {}).get("status") != "met"):
            raise ValueError("Original Native physical source missing: " + slug)
        context = read(folder / "yield_context.json")
        if (context.get("source_kind") != "original_native_yield_crosswalk_readback" or
                context.get("safety_stop_required") != "unassessed"):
            raise ValueError("Original yield source or unresolved safety context differs")
        histories.append(rows(folder / "yield_motion.jsonl"))
        hashes.append({"result": sha(result_path), "motion": sha(folder / "yield_motion.jsonl"),
                       "map": sha(folder / "road.xodr"),
                       "sign": sha(folder / "yield_sign.json"),
                       "crosswalk": sha(folder / "near_crosswalk.json"),
                       "safety": sha(folder / "safety_context.json")})
    if any(hashes[0][key] != hashes[1][key] for key in ("map", "sign", "crosswalk", "safety")):
        raise ValueError("Fixed source geometry or context changed")
    verify_rows(*histories)
    values = verify_contrast(*histories)
    report = {"format": "worker-yield-crosswalk-comparison-audit", "passed": True,
        "comparison_id": GROUP, "case_ids": [AID + "__" + slug for slug in SUFFIXES],
        "source_sha256": hashes, "measurement": values,
        "fixed_conditions": ["cell geometry", "actor", "governing yield sign",
            "near-side crosswalk", "intersecting traffic", "weather", "four cameras", "600-frame clock"],
        "deliberate_differences": ["conditional_stop_position"],
        "physical_or_legal_acceptance_claimed_by_fixture": False}
    output = Path(output)
    if output.exists():
        raise ValueError("Retain previous comparison audit")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    return report


def selftest(negative):
    verify_requests()
    values = [rows(HERE / "selected-source" / slug / "yield_motion.jsonl") for slug in SUFFIXES]
    if negative:
        values = copy.deepcopy(values)
        values[1][250]["intersecting_vehicle_y_m"] += 3
        verify_rows(*values)
        raise AssertionError("Changed intersecting traffic unexpectedly accepted")
    verify_rows(*values)
    measured = verify_contrast(*values)
    print(json.dumps({"comparison_id": GROUP, "passed": True,
                      "measurement": measured, "diagnostic_only": True}, sort_keys=True))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--comparison", choices=(GROUP,), required=True)
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--negative", action="store_true")
    parser.add_argument("--attempt", action="append")
    parser.add_argument("--output")
    args = parser.parse_args()
    selftest(args.negative) if args.self_test else audit(args.attempt or [], args.output)
