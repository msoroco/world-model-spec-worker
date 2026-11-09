"""Independent exact offline check of copied source, grade and swept requests."""
import hashlib
import json
import math
from pathlib import Path
import xml.etree.ElementTree as ET
from build import CASES, FRAMES, PLAN, POLICIES, RATE, SOURCE, SOURCE_SHA, elevation, road, rows


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def check(bundle):
    bundle = Path(bundle)
    cfg = json.loads((bundle / "config.json").read_text())
    suffix = cfg["case_id"].split("__")[-1]
    candidate = cfg["candidate_id"]
    if suffix not in CASES or candidate not in POLICIES:
        raise ValueError("Unknown case or candidate")
    if (sha(SOURCE) != SOURCE_SHA or (bundle / "assignment-source.json").read_bytes() != SOURCE.read_bytes() or
            (bundle / "case-plan.json").read_bytes() != PLAN.read_bytes()):
        raise ValueError("Copied frozen source or plan changed")
    source = json.loads(SOURCE.read_text())
    plan = json.loads(PLAN.read_text())
    law = source["law_record"]["text"]
    speed, camera, stop = POLICIES[candidate]
    if (cfg["format"] != "c104496-crest-request-v1" or
            cfg["assignment_id"] != source["assignment_id"] or
            cfg["case_id"] != source["assignment_id"] + "__" + suffix or
            cfg["source_text"] != law or plan["source_law_text"] != law or
            cfg["assignment_sha256"] != SOURCE_SHA or cfg["case_plan_sha256"] != sha(PLAN) or
            cfg["road_sha256"] != sha(bundle / "crest.xodr") or
            cfg["tracks_sha256"] != sha(bundle / "requested-tracks.jsonl") or
            cfg["rate_hz"] != RATE or cfg["frames"] != FRAMES or
            cfg["crest_station_m"] != 200 or cfg["grade_height_m"] != CASES[suffix] or
            cfg["requested_speed_mps"] != speed or cfg["camera_policy"] != camera or
            cfg["stop_before_crest"] is not stop or
            cfg["status"] != "unselected_native_request" or
            cfg["original_native_observed"] is not False or cfg["legal_verdict"] is not None):
        raise ValueError("Source join, policy, or evidence status changed")
    if (bundle / "crest.xodr").read_text() != road(CASES[suffix]):
        raise ValueError("Authored road bytes changed")
    root = ET.parse(bundle / "crest.xodr").getroot()
    geom = root.find("./road/planView/geometry")
    ep = root.find("./road/elevationProfile/elevation")
    lanes = root.findall("./road/lanes/laneSection/*/lane")
    if (geom is None or geom.get("length") != "450" or geom.find("line") is None or
            ep is None or len(lanes) != 3 or
            {(x.get("id"), x.get("type")) for x in lanes} !=
            {("1", "driving"), ("0", "none"), ("-1", "driving")} or
            abs(float(ep.get("b")) - CASES[suffix] / 100) > 1e-8 or
            abs(float(ep.get("c")) + CASES[suffix] / 40000) > 1e-8):
        raise ValueError("Crest or lane geometry changed")
    actual = [json.loads(x) for x in (bundle / "requested-tracks.jsonl").read_text().splitlines()]
    if actual != rows(suffix, candidate):
        raise ValueError("Requested 700-frame swept path changed")
    phases = {r["requested_motion_phase"] for r in actual}
    if stop:
        if "stop_before_crest" not in phases or "reverse_right" in phases:
            raise ValueError("Stop fallback changed")
    elif not {"forward_left", "reverse_right", "forward_left_finish", "opposite_direction"} <= phases:
        raise ValueError("Three-point reverse path absent")
    for r in actual:
        x, y, z = r["requested_ego_xyz_m"]
        ox, oy, oz = r["requested_other_vehicle_xyz_m"]
        if not (0 <= x <= 450 and -4.5 <= y <= 4.5 and
                abs(z - elevation(x, CASES[suffix])) < 2e-6 and
                oy == 1.75 and abs(oz - elevation(ox, CASES[suffix])) < 2e-6):
            raise ValueError("Swept path outside authored road or grade")
    if actual[100]["requested_other_vehicle_xyz_m"][0] <= actual[0]["requested_other_vehicle_xyz_m"][0]:
        raise ValueError("Other vehicle is not approaching")
    return {"case_id": cfg["case_id"], "candidate": candidate,
            "requested_phases": sorted(phases), "original_visibility_verified": False,
            "delivery_ready": False}
