"""Exact copied-source check for C109137 request packages."""
import argparse
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET

from build import ASSIGNMENT_SHA, CASES, FRAMES, LAW_SHA, PLAN_SHA, POLICIES, RATE, request_rows, road


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def check(bundle):
    bundle = Path(bundle)
    cfg = json.loads((bundle / "config.json").read_text())
    a = json.loads((bundle / "assignment-source.json").read_text())
    plan = json.loads((bundle / "case-plan.json").read_text())
    suffix = cfg["case_id"].split("__")[-1]
    candidate = cfg["candidate_id"]
    law = a["law_record"]["text"]
    if (suffix not in CASES or candidate not in POLICIES or
            sha(bundle / "assignment-source.json") != ASSIGNMENT_SHA or
            sha(bundle / "case-plan.json") != PLAN_SHA or
            hashlib.sha256(law.encode()).hexdigest() != LAW_SHA or
            cfg["source_text"] != law or plan["source_law"]["text"] != law or
            cfg["case_id"] != a["assignment_id"] + "__" + suffix or
            cfg["assignment_id"] != a["assignment_id"] or
            a["actor"] != "motor_vehicle_driver" or
            a["cell"]["layout"] != "intersection" or
            a["cell"]["maneuver"] != "enter_road" or
            a["cell"]["control"] != "pavement_striping"):
        raise ValueError("Frozen source, actor or cell changed")
    for key, name in (("assignment_sha256", "assignment-source.json"),
                      ("case_plan_sha256", "case-plan.json"),
                      ("road_sha256", "zone-adjoining.xodr"),
                      ("tracks_sha256", "requested-tracks.jsonl")):
        if cfg[key] != sha(bundle / name):
            raise ValueError("Copied source hash changed: " + name)
    if (bundle / "zone-adjoining.xodr").read_text() != road():
        raise ValueError("Authored road source changed")
    root = ET.parse(bundle / "zone-adjoining.xodr").getroot()
    roads = {x.get("id"): x for x in root.findall("./road")}
    junctions = root.findall("./junction")
    marking = roads["217"].find("./lanes/laneSection/center/lane/roadMark")
    connection = junctions[0].find("./connection") if len(junctions) == 1 else None
    if (set(roads) != {"217", "218"} or marking.get("type") != "solid solid" or
            marking.get("color") != "yellow" or connection is None or
            connection.get("incomingRoad") != "217" or
            connection.get("connectingRoad") != "218" or
            connection.find("./laneLink").get("from") != "-1"):
        raise ValueError("Authored stripe or adjoining road topology changed")
    speed, camera, stop = POLICIES[candidate]
    if (cfg["format"] != "c109137-zone-native-request-v1" or
            cfg["rate_hz"] != RATE or cfg["frames"] != FRAMES or
            cfg["requested_speed_mps"] != speed or cfg["camera_policy"] != camera or
            cfg["stop_before_stripe_x_m"] != stop or
            cfg["signal_onset_frame"] != (60 if suffix == "probe_1" else None) or
            cfg["ego_blueprint"] != "vehicle.tesla.model3" or
            cfg["main_road_id"] != 217 or cfg["adjoining_road_id"] != 218 or
            cfg["stripe_y_m"] != 0 or
            cfg["zone_legally_designated"] is not False or
            cfg["original_native_observed"] is not False or
            cfg["status"] != "unselected_native_request"):
        raise ValueError("Candidate policy or unverified status changed")
    rows = [json.loads(x) for x in (bundle / "requested-tracks.jsonl").read_text().splitlines()]
    if rows != request_rows(suffix, candidate):
        raise ValueError("400 request rows changed")
    crosses = any(r["requested_ego_xy_m"][1] > 0 for r in rows)
    first_cross = next((r["frame"] for r in rows if r["requested_ego_xy_m"][1] > 0), None)
    if candidate == "fallback3":
        if crosses or not any(r["requested_speed_mps"] == 0 for r in rows):
            raise ValueError("Stop-before-stripe fallback changed")
    elif not crosses:
        raise ValueError("Adjoining-highway crossing request absent")
    if suffix == "probe_1":
        if first_cross is not None and first_cross <= 60:
            raise ValueError("Prior indicator onset not requested")
        if any(r["requested_left_indicator"] != (r["frame"] >= 60) for r in rows):
            raise ValueError("Prior indicator request changed")
    elif any(r["requested_left_indicator"] for r in rows):
        raise ValueError("Unsignaled comparison request changed")
    return {
        "case_id": cfg["case_id"], "candidate_id": candidate,
        "requested_crossing_frame": first_cross,
        "requested_signal_onset_frame": cfg["signal_onset_frame"],
        "zone_legally_designated": False,
        "physical_crossing_observed": False,
        "delivery_ready": False}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--bundle", type=Path, default=Path.cwd())
    print(json.dumps(check(parser.parse_args().bundle)))
