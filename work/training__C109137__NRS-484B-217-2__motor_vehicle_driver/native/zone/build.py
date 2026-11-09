"""Unselected no-passing-zone crossing requests, pinned to C109137 source."""
import hashlib
import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent
CASE = HERE.parent.parent
ROOT = CASE.parents[1]
ASSIGNMENT_SHA = "a681240f21707409e973168946afc2944b800e337a04cc12580542df6657d6f0"
LAW_SHA = "d00bf2542a89af95bac14f1c81f22d0a0c54cbfe1ac7cf868dfa76df2669fd0e"
PLAN_SHA = "dfb7b614785f23960fc4a4eac4cd858f75673f451149a75d938354c1a348f226"
RATE = 20
FRAMES = 400
STRIPE_Y = 0.0
TURN_X = 50.0
POLICIES = {
    "primary": (5.0, "standard", None),
    "fallback1": (3.0, "standard", None),
    "fallback2": (5.0, "elevated", None),
    "fallback3": (5.0, "standard", 40.0),
}
CASES = ("probe_1", "probe_2")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def put(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, sort_keys=True, allow_nan=False) + "\n")


def road():
    return '''<?xml version="1.0" encoding="UTF-8"?>
<OpenDRIVE><header revMajor="1" revMinor="4" name="C109137 striped-zone intersection request" version="1.00" date="2026-11-08" north="35" south="-5" east="160" west="0" vendor="worker"/>
<road name="west two-way highway with no-passing striping" length="50" id="217" junction="-1">
<link><successor elementType="junction" elementId="1"/></link>
<type s="0" type="town"><speed max="25" unit="mph"/></type>
<planView><geometry s="0" x="0" y="0" hdg="0" length="50"><line/></geometry></planView>
<lanes><laneSection s="0"><center><lane id="0" type="none" level="false"><roadMark sOffset="0" type="solid solid" color="yellow" width="0.15"/></lane></center>
<left><lane id="1" type="driving" level="false"><width sOffset="0" a="3.5" b="0" c="0" d="0"/><roadMark sOffset="0" type="solid" color="white" width="0.12"/></lane></left>
<right><lane id="-1" type="driving" level="false"><width sOffset="0" a="3.5" b="0" c="0" d="0"/><roadMark sOffset="0" type="solid" color="white" width="0.12"/></lane></right></laneSection></lanes><objects/><signals/></road>
<road name="east two-way continuation" length="105" id="219" junction="-1">
<link><predecessor elementType="junction" elementId="1"/></link>
<type s="0" type="town"><speed max="25" unit="mph"/></type>
<planView><geometry s="0" x="55" y="0" hdg="0" length="105"><line/></geometry></planView>
<lanes><laneSection s="0"><center><lane id="0" type="none" level="false"><roadMark sOffset="0" type="solid solid" color="yellow" width="0.15"/></lane></center>
<left><lane id="1" type="driving" level="false"><width sOffset="0" a="3.5" b="0" c="0" d="0"/><roadMark sOffset="0" type="solid" color="white" width="0.12"/></lane></left>
<right><lane id="-1" type="driving" level="false"><width sOffset="0" a="3.5" b="0" c="0" d="0"/><roadMark sOffset="0" type="solid" color="white" width="0.12"/></lane></right></laneSection></lanes><objects/><signals/></road>
<road name="adjoining highway north" length="30" id="218" junction="-1">
<link><predecessor elementType="junction" elementId="1"/></link>
<type s="0" type="town"><speed max="20" unit="mph"/></type>
<planView><geometry s="0" x="53.5" y="3.5" hdg="1.5707963267948966" length="30"><line/></geometry></planView>
<lanes><laneSection s="0"><center><lane id="0" type="none" level="false"><roadMark sOffset="0" type="solid" color="yellow" width="0.15"/></lane></center>
<right><lane id="-1" type="driving" level="false"><width sOffset="0" a="3.5" b="0" c="0" d="0"/><roadMark sOffset="0" type="solid" color="white" width="0.12"/></lane></right></laneSection></lanes><objects/><signals/></road>
<road name="junction straight connector with continued striping" length="5" id="220" junction="1">
<link><predecessor elementType="road" elementId="217" contactPoint="end"/><successor elementType="road" elementId="219" contactPoint="start"/></link>
<planView><geometry s="0" x="50" y="0" hdg="0" length="5"><line/></geometry></planView>
<lanes><laneSection s="0"><center><lane id="0" type="none" level="false"><roadMark sOffset="0" type="solid solid" color="yellow" width="0.15"/></lane></center>
<left><lane id="1" type="driving" level="false"><link><predecessor id="1"/><successor id="1"/></link><width sOffset="0" a="3.5" b="0" c="0" d="0"/></lane></left>
<right><lane id="-1" type="driving" level="false"><link><predecessor id="-1"/><successor id="-1"/></link><width sOffset="0" a="3.5" b="0" c="0" d="0"/></lane></right></laneSection></lanes><objects/><signals/></road>
<road name="junction left-turn connector" length="5.497787143782138" id="221" junction="1">
<link><predecessor elementType="road" elementId="217" contactPoint="end"/><successor elementType="road" elementId="218" contactPoint="start"/></link>
<planView><geometry s="0" x="50" y="0" hdg="0" length="5.497787143782138"><arc curvature="0.2857142857142857"/></geometry></planView>
<lanes><laneSection s="0"><center><lane id="0" type="none" level="false"/></center>
<right><lane id="-1" type="driving" level="false"><link><predecessor id="-1"/><successor id="-1"/></link><width sOffset="0" a="3.5" b="0" c="0" d="0"/></lane></right></laneSection></lanes><objects/><signals/></road>
<junction name="main highway to adjoining highway" id="1">
<connection id="0" incomingRoad="217" connectingRoad="220" contactPoint="start"><laneLink from="-1" to="-1"/></connection>
<connection id="1" incomingRoad="217" connectingRoad="221" contactPoint="start"><laneLink from="-1" to="-1"/></connection>
<connection id="2" incomingRoad="219" connectingRoad="220" contactPoint="end"><laneLink from="1" to="1"/></connection>
</junction></OpenDRIVE>
'''


def request_rows(suffix, candidate):
    speed, _, stop_x = POLICIES[candidate]
    signaled = suffix == "probe_1"
    result = []
    for frame in range(FRAMES):
        t = (frame + 1) / RATE
        distance = speed * t
        if stop_x is not None:
            x = min(stop_x, 10 + distance)
            y = -1.75
            target_speed = 0 if x >= stop_x else speed
        elif distance <= 40:
            x, y, target_speed = 10 + distance, -1.75, speed
        elif distance <= 40 + 5.25 * math.pi / 2:
            angle = (distance - 40) / 5.25
            x = TURN_X + 5.25 * math.sin(angle)
            y = 3.5 - 5.25 * math.cos(angle)
            target_speed = speed
        else:
            x, y, target_speed = 55.25, 3.5 + distance - 40 - 5.25 * math.pi / 2, speed
        result.append({
            "frame": frame, "time_s": t, "case_suffix": suffix,
            "requested_ego_xy_m": [round(x, 6), round(y, 6)],
            "requested_speed_mps": target_speed,
            "requested_left_indicator": signaled and frame >= 60,
            "requested_signal_onset_frame": 60 if signaled else None,
            "requested_oncoming_xy_m": [round(135 - 4 * t, 6), 1.75],
            "requested_following_xy_m": [round(2 * t, 6), -1.75],
            "requested_adjoining_road_id": 218,
            "zone_legally_designated": False,
            "physical_stripe_crossing_observed": False,
            "traffic_impediment_reviewed": False,
            "legal_verdict": None})
    return result


def build():
    source = ROOT / "inputs" / CASE.name / "assignment.json"
    plan_path = CASE / "case-plan.json"
    a, plan = json.loads(source.read_text()), json.loads(plan_path.read_text())
    law = a["law_record"]["text"]
    if (sha(source) != ASSIGNMENT_SHA or sha(plan_path) != PLAN_SHA or
            hashlib.sha256(law.encode()).hexdigest() != LAW_SHA or
            plan["source_law"]["text"] != law or
            a["cell"]["layout"] != "intersection" or
            a["cell"]["maneuver"] != "enter_road" or
            a["cell"]["control"] != "pavement_striping" or
            a["actor"] != "motor_vehicle_driver"):
        raise ValueError("Frozen C109137 law, actor or cell changed")
    road_path = HERE / "zone-adjoining.xodr"
    road_path.write_text(road())
    entries = []
    for suffix in CASES:
        for candidate, (speed, camera, stop) in POLICIES.items():
            bundle = HERE / "drafts" / suffix / candidate
            bundle.mkdir(parents=True, exist_ok=True)
            tracks = bundle / "requested-tracks.jsonl"
            tracks.write_text("".join(json.dumps(row, sort_keys=True) + "\n"
                                      for row in request_rows(suffix, candidate)))
            (bundle / "assignment-source.json").write_bytes(source.read_bytes())
            (bundle / "case-plan.json").write_bytes(plan_path.read_bytes())
            (bundle / "zone-adjoining.xodr").write_text(road())
            cfg = {
                "format": "c109137-zone-native-request-v1",
                "assignment_id": CASE.name, "case_id": CASE.name + "__" + suffix,
                "candidate_id": candidate, "assignment_sha256": sha(source),
                "case_plan_sha256": sha(plan_path),
                "road_sha256": sha(road_path), "tracks_sha256": sha(tracks),
                "source_text": law, "rate_hz": RATE, "frames": FRAMES,
                "requested_speed_mps": speed, "camera_policy": camera,
                "stop_before_stripe_x_m": stop, "signal_onset_frame": 60 if
                    suffix == "probe_1" else None,
                "ego_blueprint": "vehicle.tesla.model3", "main_road_id": 217,
                "adjoining_road_id": 218, "stripe_y_m": STRIPE_Y,
                "zone_legally_designated": False,
                "original_native_observed": False,
                "status": "unselected_native_request"}
            put(bundle / "config.json", cfg)
            entries.append({
                "case_id": cfg["case_id"], "candidate_id": candidate,
                "config_sha256": sha(bundle / "config.json"),
                "tracks_sha256": sha(tracks)})
    manifest = {
        "format": "c109137-zone-native-construction-v1",
        "assignment_id": CASE.name, "assignment_sha256": sha(source),
        "case_plan_sha256": sha(plan_path), "road_sha256": sha(road_path),
        "entries": entries, "original_native_observed": False,
        "delivery_ready": False}
    put(HERE / "manifest.json", manifest)
    return manifest


if __name__ == "__main__":
    print(json.dumps({"requests": len(build()["entries"])}))
