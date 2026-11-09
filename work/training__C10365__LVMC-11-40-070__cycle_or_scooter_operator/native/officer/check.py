"""Offline check for exact copied C10365 candidate sources."""
import argparse
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET

from build import ASSIGNMENT_SHA, CASES, DEVICE_X, FRAMES, POLICIES, RATE, requested_rows, road


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def check(bundle):
    bundle = Path(bundle)
    cfg = json.loads((bundle / "config.json").read_text())
    a = json.loads((bundle / "assignment-source.json").read_text())
    p = json.loads((bundle / "case-plan.json").read_text())
    suffix = cfg["case_id"].split("__")[-1]
    candidate = cfg["candidate_id"]
    law = a["law_record"]["text"]
    if (suffix not in CASES or candidate not in POLICIES or
            sha(bundle / "assignment-source.json") != ASSIGNMENT_SHA or
            cfg["assignment_id"] != a["assignment_id"] or
            cfg["case_id"] != a["assignment_id"] + "__" + suffix or
            cfg["source_text"] != law or p["statutory_text"] != law or
            a["cell"]["layout"] != "alley" or a["cell"]["maneuver"] != "travel" or
            a["cell"]["control"] != "police_officer" or
            a["actor"] != "cycle_or_scooter_operator" or
            "unless otherwise directed by a Police Officer" not in law):
        raise ValueError("Exact law, actor, branch or cell changed")
    for key, name in (("assignment_sha256", "assignment-source.json"),
                      ("case_plan_sha256", "case-plan.json"),
                      ("road_sha256", "alley-stop.xodr"),
                      ("tracks_sha256", "requested-tracks.jsonl")):
        if cfg[key] != sha(bundle / name):
            raise ValueError("Copied source hash " + name)
    if (bundle / "alley-stop.xodr").read_text() != road():
        raise ValueError("Authored topology changed")
    root = ET.parse(bundle / "alley-stop.xodr").getroot()
    signal = root.find("./road/signals/signal")
    if (root.find("./road").get("id") != "365" or
            signal is None or signal.get("id") != "3651" or
            signal.get("type") != "206" or signal.get("s") != "50" or
            [lane.get("id") for lane in root.findall("./road/lanes/laneSection/right/lane")] != ["-1"]):
        raise ValueError("Road, lane or cue source")
    policy = POLICIES[candidate]
    if (cfg["format"] != "c10365-officer-native-request-v1" or
            cfg["rate_hz"] != RATE or cfg["frames"] != FRAMES or
            cfg["device_id"] != "3651" or cfg["device_station_x_m"] != DEVICE_X or
            cfg["rider_blueprint"] != "vehicle.bh.crossbike" or
            cfg["officer_blueprint_filter"] != "walker.pedestrian.*" or
            cfg["officer_position_xy_m"] != [policy["officer_x"], policy["officer_y"]] or
            cfg["officer_cue_requested"] != CASES[suffix] or
            cfg["camera_policy"] != policy["view"] or
            cfg["requested_speed_mps"] != policy["speed"] or
            cfg["officer_role_verified"] is not False or
            cfg["officer_direction_observed"] is not None or
            cfg["official_device_verified"] is not False or
            cfg["original_native_observed"] is not False or
            cfg["status"] != "unselected_native_request"):
        raise ValueError("Candidate policy or unverified status")
    rows = [json.loads(x) for x in (bundle / "requested-tracks.jsonl").read_text().splitlines()]
    if rows != requested_rows(suffix, candidate):
        raise ValueError("Source-bound requested frames")
    stop = sum(row["requested_speed_mps"] == 0 for row in rows)
    crossing = any(row["requested_rider_x_m"] > DEVICE_X for row in rows)
    if suffix == "probe_a" and (stop == 0 or crossing):
        raise ValueError("Ordinary request trajectory")
    if suffix == "probe_b" and (stop or not crossing):
        raise ValueError("Officer exception request trajectory")
    return {"case_id": cfg["case_id"], "candidate_id": candidate,
            "requested_stop_frames": stop, "requested_crossing": crossing,
            "officer_direction_observed": None, "legal_verdict": None,
            "delivery_ready": False}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--bundle", type=Path, required=True)
    print(json.dumps(check(parser.parse_args().bundle)))
