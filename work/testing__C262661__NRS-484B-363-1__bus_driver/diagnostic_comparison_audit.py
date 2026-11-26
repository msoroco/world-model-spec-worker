"""Check exact diagnostic pair interventions; original comparison audit remains separate."""
import argparse
import hashlib
import json
from pathlib import Path
import statistics

from diagnostic_delivery_audit import audit as source_audit
from comparison_audit import CHANGES


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def audit(comparison_id, left, right):
    here = Path(__file__).resolve().parent
    plan = json.loads((here / "case-plan.json").read_text())
    match = [x for x in plan["comparisons"] if x["comparison_id"] == comparison_id]
    if len(match) != 1 or comparison_id not in CHANGES:
        raise ValueError("unknown exact school-bus comparison")
    pair = match[0]
    aroot, broot = Path(left), Path(right)
    for case_id, root in zip(pair["case_ids"], (aroot, broot)):
        source_audit(case_id, root)
    a = json.loads((aroot / "context.json").read_text())
    b = json.loads((broot / "context.json").read_text())
    ac = json.loads((aroot / "config.json").read_text())["case"]
    bc = json.loads((broot / "config.json").read_text())["case"]
    ar = [json.loads(x) for x in (aroot / "original-trace.jsonl").read_text().splitlines()]
    br = [json.loads(x) for x in (broot / "original-trace.jsonl").read_text().splitlines()]
    changed = [key for key in ("speed_target_mph", "session_request", "time_request",
                               "beacon_or_sign_request", "zone_request", "children_request",
                               "vehicle_request") if ac[key] != bc[key]]
    if not changed:
        raise ValueError("comparison has no requested intervention")
    field = CHANGES[comparison_id][0]
    expected = {"speed": "speed_target_mph", "session": "session_request",
                "clock": "time_request", "lamps": "beacon_or_sign_request",
                "sign": "beacon_or_sign_request", "lamp_count": "beacon_or_sign_request",
                "alternation": "beacon_or_sign_request", "zone": "zone_request",
                "children": "children_request", "vehicle": "vehicle_request"}[field]
    if changed != [expected]:
        raise ValueError("undeclared diagnostic intervention: " + repr(changed))
    if (len(ar) != len(br) or
            json.loads((aroot / "cameras.json").read_text())["views"] !=
            json.loads((broot / "cameras.json").read_text())["views"]):
        raise ValueError("fixed diagnostic frame/camera protocol changed")
    if field == "speed":
        if statistics.median(x["bus_speed_mps"] for x in ar) >= statistics.median(
                x["bus_speed_mps"] for x in br):
            raise ValueError("diagnostic speed order absent")
    elif field == "session" and a["school_in_session_today"] == b["school_in_session_today"]:
        raise ValueError("diagnostic session contrast absent")
    elif field == "clock" and a["time_window_label"] == b["time_window_label"]:
        raise ValueError("diagnostic clock contrast absent")
    elif field in ("lamps", "lamp_count", "alternation") and [
            x["beacon_yellow_lights_lit"] for x in ar] == [
            x["beacon_yellow_lights_lit"] for x in br]:
        raise ValueError("diagnostic lamp contrast absent")
    elif field == "sign" and [x["sign_limit_active"] for x in ar] == [
            x["sign_limit_active"] for x in br]:
        raise ValueError("diagnostic sign contrast absent")
    elif field == "zone" and [x["inside_designated_zone"] for x in ar] == [
            x["inside_designated_zone"] for x in br]:
        raise ValueError("diagnostic zone contrast absent")
    return {"comparison_id": comparison_id, "case_ids": pair["case_ids"],
            "left_context_sha256": sha(aroot / "context.json"),
            "right_context_sha256": sha(broot / "context.json"),
            "requested_difference_checked": changed, "diagnostic_observed_channel_checked":
            field not in ("children", "vehicle"), "fixed_camera_protocol_checked": True,
            "original_physical_difference_unverified": True,
            "legal_judgment": "unresolved"}


def main():
    p = argparse.ArgumentParser()
    for flag in ("comparison", "left", "right", "output"):
        p.add_argument("--" + flag, required=True)
    a = p.parse_args()
    Path(a.output).write_text(json.dumps(audit(a.comparison, a.left, a.right), sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
