"""Source-bound preflight for the two controlled traffic-response cases."""
import hashlib
import json
from pathlib import Path

FRAMES = 600
RATE = 20
ASSIGNMENT = "training__C109137__NRS-484B-217-2__motor_vehicle_driver"
CASES = {"traffic_clear_traffic", "traffic_following_brake"}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def check(bundle):
    bundle = Path(bundle)
    cfg = json.loads((bundle / "config.json").read_text())
    assignment = json.loads((bundle / "assignment-source.json").read_text())
    plan = json.loads((bundle / "case-plan.json").read_text())
    suffix = cfg.get("case_id", "").removeprefix(ASSIGNMENT + "__")
    if (cfg.get("assignment_id") != ASSIGNMENT or suffix not in CASES or
            cfg.get("candidate_id") != "primary" or cfg.get("traffic_policy") != suffix or
            cfg.get("rate_hz") != RATE or cfg.get("frames") != FRAMES or
            cfg.get("source_text") != assignment["law"]["text"] or
            plan["source_law"]["text"] != assignment["law"]["text"] or
            assignment.get("actor") != "motor_vehicle_driver" or
            any(assignment.get("cell", {}).get(key) != value for key, value in
                (("cell_id", "C109137"), ("layout", "intersection"),
                 ("maneuver", "enter_road"), ("control", "pavement_striping")))):
        raise ValueError("Traffic frozen source or exact case differs")
    for key, name in (("assignment_sha256", "assignment-source.json"),
                      ("case_plan_sha256", "case-plan.json"),
                      ("road_sha256", "zone-adjoining.xodr"),
                      ("tracks_sha256", "requested-tracks.jsonl")):
        if cfg.get(key) != sha(bundle / name):
            raise ValueError("Traffic copied source hash changed: " + name)
    rows = [json.loads(line) for line in (bundle / "requested-tracks.jsonl").read_text().splitlines()]
    if len(rows) != FRAMES:
        raise ValueError("Traffic request needs 600 frames")
    for index, row in enumerate(rows):
        if (row.get("frame") != index or row.get("case_suffix") != suffix or
                row.get("requested_left_indicator") != (index >= 60) or
                row.get("requested_following_speed_mps") !=
                (1 if suffix == "traffic_following_brake" and index >= 172 else 2)):
            raise ValueError("Traffic request frame, indicator or response differs")
    return {"case_id": cfg["case_id"], "candidate_id": "primary",
            "requested_frames": FRAMES, "traffic_policy": suffix,
            "requested_crossing_frame": 172, "physical_crossing_observed": False,
            "delivery_ready": False}
