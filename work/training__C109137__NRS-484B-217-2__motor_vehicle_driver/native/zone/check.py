"""Exact copied-source check for C109137 request packages."""
import argparse
import hashlib
import json
import math
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
    if set(roads) != {"217", "218", "219", "220", "221"} or len(junctions) != 1:
        raise ValueError("Authored road set or junction changed")
    for rid in ("217", "219", "220"):
        marking = roads[rid].find("./lanes/laneSection/center/lane/roadMark")
        if marking is None or marking.get("type") != "solid solid" or marking.get("color") != "yellow":
            raise ValueError("No-passing striping discontinuity")
    links = {
        "217": (None, ("junction", "1", None)),
        "219": (("junction", "1", None), None),
        "218": (("junction", "1", None), None),
        "220": (("road", "217", "end"), ("road", "219", "start")),
        "221": (("road", "217", "end"), ("road", "218", "start")),
    }
    for rid, (predecessor, successor) in links.items():
        r = roads[rid]
        if r.get("junction") != ("1" if rid in ("220", "221") else "-1"):
            raise ValueError("Connecting road junction membership")
        for role, expected in (("predecessor", predecessor), ("successor", successor)):
            actual = r.find("./link/" + role)
            if expected is None:
                if actual is not None:
                    raise ValueError("Unexpected road link")
            elif actual is None or (actual.get("elementType"), actual.get("elementId"),
                    actual.get("contactPoint")) != expected:
                raise ValueError("Road/junction linkage changed")
    connections = [
        (c.get("incomingRoad"), c.get("connectingRoad"), c.get("contactPoint"),
         c.find("./laneLink").get("from"), c.find("./laneLink").get("to"))
        for c in junctions[0].findall("./connection")]
    if connections != [("217", "220", "start", "-1", "-1"),
                       ("217", "221", "start", "-1", "-1"),
                       ("219", "220", "end", "1", "1")]:
        raise ValueError("Junction connection or lane links changed")
    arc = roads["221"].find("./planView/geometry")
    if (arc is None or abs(float(arc.get("length")) - 3.5 * math.pi / 2) > 1e-8 or
            abs(float(arc.find("./arc").get("curvature")) - 1/3.5) > 1e-8 or
            float(arc.get("x")) != 50 or float(arc.get("y")) != 0 or
            float(roads["218"].find("./planView/geometry").get("x")) != 53.5 or
            float(roads["218"].find("./planView/geometry").get("y")) != 3.5):
        raise ValueError("Left turn arc/adjoining road geometry changed")
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
