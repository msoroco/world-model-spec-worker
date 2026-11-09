"""Source-pinned, unselected bicycle/officer alley capture requests."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
CASE = HERE.parent.parent
ROOT = CASE.parents[1]
ASSIGNMENT_SHA = "58c5a14d7c38851c0672c4e8cb5cf02eede790eec53a8fd6d5ffd541893c8419"
RATE = 20
FRAMES = 480
DEVICE_X = 50.0
STOP_X = 44.0
POLICIES = {
    "primary": {"speed": 4.0, "view": "standard", "officer_x": 39.0, "officer_y": -8.0},
    "fallback1": {"speed": 2.5, "view": "standard", "officer_x": 39.0, "officer_y": -8.0},
    "fallback2": {"speed": 4.0, "view": "elevated", "officer_x": 39.0, "officer_y": -8.0},
    "fallback3": {"speed": 4.0, "view": "standard", "officer_x": 35.0, "officer_y": -5.0},
}
CASES = {"probe_a": "no_contrary_direction", "probe_b": "proceed_request"}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_json(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, sort_keys=True, allow_nan=False) + "\n")


def road():
    return '''<?xml version="1.0" encoding="UTF-8"?>
<OpenDRIVE><header revMajor="1" revMinor="4" name="C10365 alley officer request" version="1.00" date="2026-11-08" north="4" south="-4" east="120" west="0" vendor="worker"/>
<road name="alley with authored stop cue" length="120" id="365" junction="-1">
<type s="0" type="town"><speed max="20" unit="mph"/></type>
<planView><geometry s="0" x="0" y="0" hdg="0" length="120"><line/></geometry></planView>
<lanes><laneSection s="0"><center><lane id="0" type="none" level="false"><roadMark sOffset="0" type="solid" color="yellow" width="0.15"/></lane></center><right><lane id="-1" type="driving" level="false"><width sOffset="0" a="3.5" b="0" c="0" d="0"/><roadMark sOffset="0" type="solid" color="white" width="0.12"/></lane></right></laneSection></lanes>
<objects/><signals><signal id="3651" name="C10365_authored_stop_cue" s="50" t="-4.2" zOffset="0" hOffset="0" pitch="0" roll="0" dynamic="no" orientation="+" country="US" type="206" subtype="0" value="0" height="0.75" width="0.75"/></signals>
</road></OpenDRIVE>
'''


def requested_rows(suffix, candidate):
    speed = POLICIES[candidate]["speed"]
    crossing = suffix == "probe_b"
    reach = (STOP_X - 5.0) / speed
    rows = []
    for frame in range(FRAMES):
        t = (frame + 1) / RATE
        if t < reach:
            x, target = 5.0 + speed * t, speed
        elif crossing:
            x, target = STOP_X + speed * (t - reach), speed
        else:
            x, target = STOP_X, 0.0
        rows.append({
            "frame": frame, "time_s": t, "requested_rider_x_m": round(x, 6),
            "requested_rider_y_m": -1.75, "requested_speed_mps": target,
            "requested_officer_cue": CASES[suffix],
            "officer_direction_observed": None, "officer_authority_verified": False,
            "official_device_verified": False, "legal_verdict": None,
        })
    return rows


def build():
    assignment = ROOT / "inputs" / CASE.name / "assignment.json"
    plan_path = CASE / "case-plan.json"
    a, plan = json.loads(assignment.read_text()), json.loads(plan_path.read_text())
    law = a["law_record"]["text"]
    if (sha(assignment) != ASSIGNMENT_SHA or plan["statutory_text"] != law or
            a["cell"]["layout"] != "alley" or a["cell"]["maneuver"] != "travel" or
            a["cell"]["control"] != "police_officer" or
            a["actor"] != "cycle_or_scooter_operator" or
            "unless otherwise directed by a Police Officer" not in law):
        raise ValueError("Frozen source or statutory branch changed")
    road_path = HERE / "alley-stop.xodr"
    road_path.write_text(road())
    entries = []
    for suffix in CASES:
        for candidate, policy in POLICIES.items():
            bundle = HERE / "drafts" / suffix / candidate
            bundle.mkdir(parents=True, exist_ok=True)
            tracks = bundle / "requested-tracks.jsonl"
            tracks.write_text("".join(json.dumps(r, sort_keys=True) + "\n"
                                      for r in requested_rows(suffix, candidate)))
            (bundle / "assignment-source.json").write_bytes(assignment.read_bytes())
            (bundle / "case-plan.json").write_bytes(plan_path.read_bytes())
            (bundle / "alley-stop.xodr").write_text(road())
            cfg = {
                "format": "c10365-officer-native-request-v1",
                "assignment_id": CASE.name, "case_id": CASE.name + "__" + suffix,
                "candidate_id": candidate, "assignment_sha256": sha(assignment),
                "case_plan_sha256": sha(plan_path), "road_sha256": sha(road_path),
                "tracks_sha256": sha(tracks), "source_text": law,
                "rate_hz": RATE, "frames": FRAMES, "device_id": "3651",
                "device_station_x_m": DEVICE_X, "rider_blueprint": "vehicle.bh.crossbike",
                "officer_blueprint_filter": "walker.pedestrian.*",
                "officer_position_xy_m": [policy["officer_x"], policy["officer_y"]],
                "officer_role_requested": "Police Officer", "officer_role_verified": False,
                "officer_cue_requested": CASES[suffix], "officer_direction_observed": None,
                "camera_policy": policy["view"], "requested_speed_mps": policy["speed"],
                "official_device_verified": False, "original_native_observed": False,
                "status": "unselected_native_request",
            }
            write_json(bundle / "config.json", cfg)
            entries.append({"case_id": cfg["case_id"], "candidate_id": candidate,
                            "config_sha256": sha(bundle / "config.json"),
                            "tracks_sha256": sha(tracks)})
    manifest = {
        "format": "c10365-officer-native-construction-v1",
        "assignment_id": CASE.name, "assignment_sha256": sha(assignment),
        "case_plan_sha256": sha(plan_path), "road_sha256": sha(road_path),
        "entries": entries, "original_native_observed": False, "delivery_ready": False,
    }
    write_json(HERE / "manifest.json", manifest)
    return manifest


if __name__ == "__main__":
    print(json.dumps({"requests": len(build()["entries"])}))
