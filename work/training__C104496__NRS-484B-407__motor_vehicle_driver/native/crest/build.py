"""Source-bound, unselected grade-crest three-point-turn requests."""
import hashlib
import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent
CASE = HERE.parents[1]
ROOT = CASE.parents[1]
SOURCE = HERE / "assignment-source.json" if (HERE / "assignment-source.json").is_file() else ROOT / "inputs" / CASE.name / "assignment.json"
PLAN = HERE / "case-plan.json" if (HERE / "case-plan.json").is_file() else CASE / "case-plan.json"
SOURCE_SHA = "d1490ce9bff6b98b001e5e12eb8498bfb028d66a236c814f81cb9e8e222b0285"
RATE = 20
FRAMES = 700
CASES = {"probe_01": 0.8, "probe_02": 12.0}
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
    path.write_text(json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + "\n")


def elevation(x, height):
    return height * (1 - ((x - 200) / 200) ** 2)


def road(height):
    slope = height / 100
    quadratic = -height / 40000
    return f'''<?xml version="1.0" encoding="UTF-8"?>
<OpenDRIVE><header revMajor="1" revMinor="4" name="C104496 authored grade crest" version="1.00" date="2026-11-08" north="8" south="-8" east="450" west="0" vendor="worker"/>
<road name="two-way graded highway" length="450" id="407" junction="-1">
<type s="0" type="rural"><speed max="25" unit="mph"/></type>
<planView><geometry s="0" x="0" y="0" hdg="0" length="450"><line/></geometry></planView>
<elevationProfile><elevation s="0" a="0" b="{slope:.9f}" c="{quadratic:.9f}" d="0"/></elevationProfile>
<lanes><laneSection s="0"><left><lane id="1" type="driving" level="false"><width sOffset="0" a="4.5" b="0" c="0" d="0"/><roadMark sOffset="0" type="solid" color="white" width="0.12"/></lane></left><center><lane id="0" type="none" level="false"><roadMark sOffset="0" type="solid" color="yellow" width="0.15"/></lane></center><right><lane id="-1" type="driving" level="false"><width sOffset="0" a="4.5" b="0" c="0" d="0"/><roadMark sOffset="0" type="solid" color="white" width="0.12"/></lane></right></laneSection></lanes><objects/><signals/></road></OpenDRIVE>
'''


def turn_pose(distance):
    """Requested swept centerline: forward left, reverse right, forward left."""
    p0 = (200 + 8 * math.sin(1.2), -1.75 + 8 * (1 - math.cos(1.2)))
    p1 = (p0[0] - 8 * (math.sin(2.0) - math.sin(1.2)),
          p0[1] + 8 * (math.cos(2.0) - math.cos(1.2)))
    if distance <= 20:
        return 180 + distance, -1.75, 0.0, "approach"
    distance -= 20
    if distance <= 9.6:
        theta = distance / 8
        return 200 + 8 * math.sin(theta), -1.75 + 8 * (1 - math.cos(theta)), theta, "forward_left"
    distance -= 9.6
    if distance <= 6.4:
        theta = 1.2 + distance / 8
        return (p0[0] - 8 * (math.sin(theta) - math.sin(1.2)),
                p0[1] + 8 * (math.cos(theta) - math.cos(1.2)), theta, "reverse_right")
    distance -= 6.4
    if distance <= 8 * (math.pi - 2):
        theta = 2 + distance / 8
        return (p1[0] + 8 * (math.sin(theta) - math.sin(2)),
                p1[1] + 8 * (math.cos(2) - math.cos(theta)), theta, "forward_left_finish")
    distance -= 8 * (math.pi - 2)
    endpoint_x = p1[0] - 8 * math.sin(2)
    endpoint_y = p1[1] + 8 * (math.cos(2) + 1)
    return endpoint_x - distance, endpoint_y, math.pi, "opposite_direction"


def rows(suffix, candidate):
    speed, _, stop = POLICIES[candidate]
    height = CASES[suffix]
    out = []
    for frame in range(FRAMES):
        t = frame / RATE
        distance = min(speed * t, 19.0) if stop else speed * t
        x, y, heading, phase = turn_pose(distance)
        other_x = min(180.0, 47.6 + 4.0 * t)
        out.append({"frame": frame, "time_s": t, "requested_ego_xyz_m": [round(x, 6), round(y, 6), round(elevation(x, height), 6)],
                    "requested_heading_rad": round(heading, 6), "requested_speed_mps": 0 if stop and speed*t >= 19 else speed,
                    "requested_motion_phase": "stop_before_crest" if stop and speed*t >= 19 else phase,
                    "requested_other_vehicle_xyz_m": [round(other_x, 6), 1.75, round(elevation(other_x, height), 6)],
                    "requested_other_vehicle_approach": "west", "other_approach_virtual_camera_x_m": 352.4,
                    "original_body_rays_observed": False, "human_visibility_reviewed": False, "legal_verdict": None})
    return out


def build():
    if sha(SOURCE) != SOURCE_SHA:
        raise ValueError("Frozen assignment changed")
    source = json.loads(SOURCE.read_text())
    plan = json.loads(PLAN.read_text())
    law = source["law_record"]["text"]
    if (plan["source_law_text"] != law or source["actor"] != "motor_vehicle_driver" or
            {k: source["cell"][k] for k in ("layout", "maneuver", "control")} !=
            {"layout": "hill_crest", "maneuver": "u_turn", "control": "other_vehicle"}):
        raise ValueError("Frozen law, actor or cell changed")
    entries = []
    for suffix, height in CASES.items():
        road_text = road(height)
        for candidate, (speed, camera, stop) in POLICIES.items():
            bundle = HERE / "drafts" / suffix / candidate
            bundle.mkdir(parents=True, exist_ok=True)
            (bundle / "assignment-source.json").write_bytes(SOURCE.read_bytes())
            (bundle / "case-plan.json").write_bytes(PLAN.read_bytes())
            (bundle / "crest.xodr").write_text(road_text)
            tracks = bundle / "requested-tracks.jsonl"
            tracks.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows(suffix, candidate)))
            cfg = {"format": "c104496-crest-request-v1", "assignment_id": CASE.name,
                   "case_id": CASE.name + "__" + suffix, "candidate_id": candidate,
                   "assignment_sha256": SOURCE_SHA, "case_plan_sha256": sha(PLAN),
                   "road_sha256": sha(bundle / "crest.xodr"), "tracks_sha256": sha(tracks),
                   "source_text": law, "rate_hz": RATE, "frames": FRAMES,
                   "crest_station_m": 200, "grade_height_m": height,
                   "requested_speed_mps": speed, "camera_policy": camera,
                   "stop_before_crest": stop, "other_vehicle_blueprint": "vehicle.audi.a2",
                   "ego_blueprint": "vehicle.tesla.model3", "status": "unselected_native_request",
                   "original_native_observed": False, "legal_verdict": None}
            put(bundle / "config.json", cfg)
            entries.append({"case_id": cfg["case_id"], "candidate_id": candidate,
                            "config_sha256": sha(bundle / "config.json"), "tracks_sha256": sha(tracks)})
    manifest = {"format": "c104496-crest-construction-v1", "assignment_id": CASE.name,
                "assignment_sha256": SOURCE_SHA, "case_plan_sha256": sha(PLAN),
                "status": "draft_not_selected", "entries": entries, "delivery_ready": False}
    put(HERE / "manifest.json", manifest)
    return manifest


if __name__ == "__main__":
    print(json.dumps({"requests": len(build()["entries"])}))
