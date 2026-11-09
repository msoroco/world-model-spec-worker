"""Unselected source-pinned U-turn requests for NRS 484B.403(3)."""
import hashlib
import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent
CASE = HERE.parent
ROOT = CASE.parents[1]
SOURCE = ROOT / "inputs" / CASE.name / "assignment.json"
PLAN = CASE / "case-plan.json"
SOURCE_SHA = "aab716c76efa01e178741ff7f706db5bf5daecf37e402616e00e146dfbd5a8cc"
FRAMES = 800
RATE = 20
CASES = {"reference": -45.0, "contrast": 0.0}
POLICIES = {"primary": (5.0, "standard", 0.0),
            "fallback1": (3.0, "standard", 0.0),
            "fallback2": (5.0, "elevated_overview", 0.0),
            "fallback3": (5.0, "standard", 2.0)}
TURN_ANGULAR_RADPS = 0.6
TURN_RADIUS_M = 6.0


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def put(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n")


def road_piece(number, name, x, y, hdg, length, junction, prev, next_):
    links = "<link>"
    if prev is not None:
        kind, ident = prev
        links += f'<predecessor elementType="{kind}" elementId="{ident}" contactPoint="end"/>'
    if next_ is not None:
        kind, ident = next_
        links += f'<successor elementType="{kind}" elementId="{ident}" contactPoint="start"/>'
    links += "</link>"
    def lane(ident):
        return (f'<lane id="{ident}" type="driving" level="false"><link><predecessor id="{ident}"/>'
                f'<successor id="{ident}"/></link><width sOffset="0" a="4" b="0" c="0" d="0"/>'
                '<roadMark sOffset="0" type="solid" color="white" width="0.12"/></lane>')
    return (f'<road id="{number}" name="{name}" length="{length}" junction="{junction}">{links}'
            f'<type s="0" type="town"><speed max="25" unit="mph"/></type>'
            f'<planView><geometry s="0" x="{x}" y="{y}" hdg="{hdg}" length="{length}"><line/></geometry></planView>'
            '<elevationProfile><elevation s="0" a="0" b="0" c="0" d="0"/></elevationProfile>'
            '<lanes><laneSection s="0"><left>' + ''.join(lane(i) for i in (1,2,3)) + '</left>'
            '<center><lane id="0" type="none" level="false"><roadMark sOffset="0" type="solid" color="yellow" width="0.15"/></lane></center>'
            '<right>' + ''.join(lane(i) for i in (-1,-2,-3)) + '</right></laneSection></lanes>'
            '<objects/><signals/></road>')


def road():
    pieces = [
        (403,"east-west west approach",-100,0,0,80,-1,None,("junction",1)),
        (404,"east-west intersection",-20,0,0,40,1,("road",403),("road",405)),
        (405,"east-west east departure",20,0,0,80,-1,("junction",1),None),
        (406,"north-south south approach",0,-100,math.pi/2,80,-1,None,("junction",1)),
        (407,"north-south intersection",0,-20,math.pi/2,40,1,("road",406),("road",408)),
        (408,"north-south north departure",0,20,math.pi/2,80,-1,("junction",1),None)]
    junction = ('<junction id="1" name="crossed streets">'
                '<connection id="1" incomingRoad="403" connectingRoad="404" contactPoint="start"><laneLink from="-3" to="-3"/></connection>'
                '<connection id="2" incomingRoad="406" connectingRoad="407" contactPoint="start"><laneLink from="-3" to="-3"/></connection></junction>')
    return ('<?xml version="1.0" encoding="UTF-8"?><OpenDRIVE><header revMajor="1" revMinor="4"'
            ' name="C111662 U-turn location request" version="1" date="2026-11-08"'
            ' north="100" south="-100" east="100" west="-100" vendor="worker"/>' +
            ''.join(road_piece(*piece) for piece in pieces) + junction + '</OpenDRIVE>\n')


def pose(t, center, speed, dwell):
    arrival = (center+80)/speed
    if t < arrival:
        return -80+speed*t, -6.0, 0.0, speed, "approach"
    if t < arrival+dwell:
        return center, -6.0, 0.0, 0.0, "pre_turn_dwell"
    turn_t = t-arrival-dwell
    angle = min(math.pi, TURN_ANGULAR_RADPS*turn_t)
    if angle < math.pi:
        return (center+TURN_RADIUS_M*math.sin(angle), -TURN_RADIUS_M*math.cos(angle),
                angle, TURN_RADIUS_M*TURN_ANGULAR_RADPS, "u_turn")
    x = max(center-speed*(turn_t-math.pi/TURN_ANGULAR_RADPS), center-12)
    return x, 6.0, math.pi, speed if x > center-12 else 0.0, "westbound_departure"


def rows(suffix, candidate):
    center, (speed, _, dwell) = CASES[suffix], POLICIES[candidate]
    result = []
    for frame in range(FRAMES):
        t = frame/RATE
        x,y,heading,velocity,phase = pose(t,center,speed,dwell)
        result.append({"frame":frame,"time_s":t,"requested_ego_xyz_m":[round(x,6),round(y,6),0],
                       "requested_heading_rad":round(heading,9),"requested_speed_mps":round(velocity,6),
                       "requested_phase":phase,"requested_turn_center_x_m":center,
                       "authored_intersection_zone_x_m":[-20,20],"authored_business_district":True,
                       "district_designation_verified":False,"intersection_exception_legally_verified":False,
                       "original_native_observed":False,"legal_verdict":None})
    return result


def build():
    if sha(SOURCE) != SOURCE_SHA:
        raise ValueError("Frozen assignment changed")
    source, plan = json.loads(SOURCE.read_text()), json.loads(PLAN.read_text())
    if (source["law_record"]["text"] != plan["source_law_text"] or
            source["actor"] != "motor_vehicle_driver" or
            {key:source["cell"][key] for key in ("layout","maneuver","control")} !=
            {"layout":"intersection","maneuver":"u_turn","control":"centerline"}):
        raise ValueError("Frozen law or cell mismatch")
    entries=[]
    for suffix in CASES:
        for candidate, (speed,camera,dwell) in POLICIES.items():
            bundle=HERE/"drafts"/suffix/candidate
            bundle.mkdir(parents=True,exist_ok=True)
            (bundle/"assignment-source.json").write_bytes(SOURCE.read_bytes())
            (bundle/"case-plan.json").write_bytes(PLAN.read_bytes())
            (bundle/"district-crossroads.xodr").write_text(road())
            track=bundle/"requested-tracks.jsonl"
            track.write_text(''.join(json.dumps(row,sort_keys=True)+'\n' for row in rows(suffix,candidate)))
            cfg={"format":"c111662-4033-native-request-v1","assignment_id":CASE.name,
                 "case_id":CASE.name+'__'+suffix,"candidate_id":candidate,
                 "assignment_sha256":SOURCE_SHA,"case_plan_sha256":sha(PLAN),
                 "road_sha256":sha(bundle/"district-crossroads.xodr"),"tracks_sha256":sha(track),
                 "source_text":source["law_record"]["text"],"frames":FRAMES,"rate_hz":RATE,
                 "requested_turn_center_x_m":CASES[suffix],"requested_approach_speed_mps":speed,
                 "camera_policy":camera,"pre_turn_dwell_s":dwell,
                 "ego_blueprint":"vehicle.tesla.model3","status":"unselected_native_request",
                 "original_native_observed":False,"legal_verdict":None}
            put(bundle/"config.json",cfg)
            entries.append({"case_id":cfg["case_id"],"candidate_id":candidate,
                            "config_sha256":sha(bundle/"config.json")})
    manifest={"format":"c111662-4033-construction-v1","assignment_id":CASE.name,
              "assignment_sha256":SOURCE_SHA,"case_plan_sha256":sha(PLAN),
              "status":"draft_not_selected","delivery_ready":False,"entries":entries}
    put(HERE/"manifest.json",manifest)
    return manifest


if __name__ == '__main__':
    print(json.dumps({"requests":len(build()["entries"])}))
