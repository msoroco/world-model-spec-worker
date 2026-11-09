"""Unselected source-pinned crossroads entry requests for NRS 484B.250(2)."""
import hashlib
import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent
CASE = HERE.parent
ROOT = CASE.parents[1]
SOURCE = ROOT / "inputs" / CASE.name / "assignment.json"
PLAN = CASE / "case-plan.json"
SOURCE_SHA = "91097a36e8dbbb1493a174ebacd22e566df58d0e914af050a9f8a8e990ed83cd"
RATE = 20
FRAMES = 600
CASES = ("controlled_1", "controlled_2")
POLICIES = {
    "primary": (5.0, "standard", False),
    "fallback1": (3.0, "standard", False),
    "fallback2": (5.0, "elevated_overview", False),
    "fallback3": (5.0, "standard", True),
}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def put(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n")


def road_element(road_id, name, x, y, heading, junction, predecessor, successor):
    link = "<link>"
    if predecessor:
        kind, ident = predecessor
        link += f'<predecessor elementType="{kind}" elementId="{ident}" contactPoint="end"/>'
    if successor:
        kind, ident = successor
        link += f'<successor elementType="{kind}" elementId="{ident}" contactPoint="start"/>'
    link += "</link>"
    lane_links = '<link><predecessor id="-1"/><successor id="-1"/></link>'
    return f'''<road id="{road_id}" name="{name}" length="40" junction="{junction}">{link}
<type s="0" type="rural"><speed max="25" unit="mph"/></type>
<planView><geometry s="0" x="{x}" y="{y}" hdg="{heading}" length="40"><line/></geometry></planView>
<elevationProfile><elevation s="0" a="0" b="0" c="0" d="0"/></elevationProfile>
<lanes><laneSection s="0"><left><lane id="1" type="driving" level="false"><width sOffset="0" a="3.5" b="0" c="0" d="0"/><roadMark sOffset="0" type="solid" color="white" width="0.12"/></lane></left>
<center><lane id="0" type="none" level="false"><roadMark sOffset="0" type="solid" color="yellow" width="0.15"/></lane></center>
<right><lane id="-1" type="driving" level="false">{lane_links}<width sOffset="0" a="3.5" b="0" c="0" d="0"/><roadMark sOffset="0" type="solid" color="white" width="0.12"/></lane></right></laneSection></lanes><objects/><signals/></road>'''


def road():
    east = [(250, "eastbound approach highway A", -60, 0, 0, -1, None, ("junction", 1)),
            (251, "eastbound junction connector", -20, 0, 0, 1, ("road", 250), ("road", 252)),
            (252, "eastbound departure highway A", 20, 0, 0, -1, ("junction", 1), None)]
    north = [(253, "northbound approach highway B", 0, -60, math.pi/2, -1, None, ("junction", 1)),
             (254, "northbound junction connector", 0, -20, math.pi/2, 1, ("road", 253), ("road", 255)),
             (255, "northbound departure highway B", 0, 20, math.pi/2, -1, ("junction", 1), None)]
    roads = "".join(road_element(*row) for row in east + north)
    junction = '''<junction id="1" name="uncontrolled crossed highways">
<connection id="1" incomingRoad="250" connectingRoad="251" contactPoint="start"><laneLink from="-1" to="-1"/></connection>
<connection id="2" incomingRoad="253" connectingRoad="254" contactPoint="start"><laneLink from="-1" to="-1"/></connection></junction>'''
    return ('<?xml version="1.0" encoding="UTF-8"?><OpenDRIVE><header revMajor="1" revMinor="4" '
            'name="C111294 two-highway entry-time request" version="1" date="2026-11-08" '
            'north="60" south="-60" east="60" west="-60" vendor="worker"/>' + roads + junction + '</OpenDRIVE>\n')


def ego_station(t, speed, yielding, stop):
    approach_time = 25 / speed
    if stop:
        return min(-50 + speed*t, -25), "stop_before_entry" if t >= approach_time else "approach"
    if yielding and t >= approach_time:
        if t < approach_time + 1:
            return -25, "yield_wait"
        t -= 1
    station = min(-50 + speed*t, 50)
    return station, "approach" if station < -20 else "intersection" if station < 20 else "departure"


def rows(suffix, candidate):
    speed, _, stop = POLICIES[candidate]
    yielding = suffix == "controlled_1"
    out = []
    for frame in range(FRAMES):
        t = frame / RATE
        ego_x, phase = ego_station(t, speed, yielding, stop)
        other_y = min(-50 + 5*t, 50)
        out.append({"frame": frame, "time_s": t,
                    "requested_ego_xyz_m": [round(ego_x, 6), -1.75, 0],
                    "requested_other_xyz_m": [1.75, round(other_y, 6), 0],
                    "requested_ego_heading_rad": 0,
                    "requested_other_heading_rad": round(math.pi/2, 9),
                    "requested_ego_speed_mps": 0 if phase in ("yield_wait", "stop_before_entry") else speed if ego_x < 50 else 0,
                    "requested_other_speed_mps": 5 if other_y < 50 else 0,
                    "requested_ego_phase": phase, "requested_other_phase": "approach" if other_y < -20 else "intersection" if other_y < 20 else "departure",
                    "requested_yield_action": yielding, "authored_official_device_count": 0,
                    "original_native_observed": False, "legal_verdict": None})
    return out


def build():
    if sha(SOURCE) != SOURCE_SHA:
        raise ValueError("Frozen assignment changed")
    source = json.loads(SOURCE.read_text())
    plan = json.loads(PLAN.read_text())
    if (plan["source_law_text"] != source["law_record"]["text"] or
            source["actor"] != "motor_vehicle_driver" or
            {k: source["cell"][k] for k in ("layout", "maneuver", "control")} !=
            {"layout": "intersection", "maneuver": "travel", "control": "other_vehicle"}):
        raise ValueError("Frozen law, actor or cell mismatch")
    entries = []
    for suffix in CASES:
        for candidate, (speed, camera, stop) in POLICIES.items():
            bundle = HERE / "drafts" / suffix / candidate
            bundle.mkdir(parents=True, exist_ok=True)
            (bundle / "assignment-source.json").write_bytes(SOURCE.read_bytes())
            (bundle / "case-plan.json").write_bytes(PLAN.read_bytes())
            (bundle / "crossroads.xodr").write_text(road())
            track = bundle / "requested-tracks.jsonl"
            track.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows(suffix, candidate)))
            cfg = {"format": "c111294-2502-native-request-v1", "assignment_id": CASE.name,
                   "case_id": CASE.name + "__" + suffix, "candidate_id": candidate,
                   "assignment_sha256": SOURCE_SHA, "case_plan_sha256": sha(PLAN),
                   "road_sha256": sha(bundle / "crossroads.xodr"), "tracks_sha256": sha(track),
                   "source_text": source["law_record"]["text"], "rate_hz": RATE, "frames": FRAMES,
                   "ego_highway_road_ids": [250, 251, 252], "right_other_highway_road_ids": [253, 254, 255],
                   "ego_entry_boundary_x_m": -20, "other_entry_boundary_y_m": -20,
                   "requested_speed_mps": speed, "camera_policy": camera,
                   "requested_yield_action": suffix == "controlled_1", "stop_before_entry": stop,
                   "ego_blueprint": "vehicle.tesla.model3", "other_blueprint": "vehicle.audi.a2",
                   "status": "unselected_native_request", "original_native_observed": False,
                   "legal_verdict": None}
            put(bundle / "config.json", cfg)
            entries.append({"case_id": cfg["case_id"], "candidate_id": candidate,
                            "config_sha256": sha(bundle / "config.json")})
    manifest = {"format": "c111294-2502-construction-v1", "assignment_id": CASE.name,
                "assignment_sha256": SOURCE_SHA, "case_plan_sha256": sha(PLAN),
                "status": "draft_not_selected", "delivery_ready": False, "entries": entries}
    put(HERE / "manifest.json", manifest)
    return manifest


if __name__ == "__main__":
    print(json.dumps({"requests": len(build()["entries"])}))
