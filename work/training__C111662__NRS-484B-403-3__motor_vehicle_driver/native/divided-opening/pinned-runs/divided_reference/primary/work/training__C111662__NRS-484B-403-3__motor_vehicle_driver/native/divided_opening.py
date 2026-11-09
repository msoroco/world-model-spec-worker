"""Source-pinned CPU construction of the separate divided-highway opening branch.

The median and opening are authored OpenDRIVE geometry. This module makes no
claim that CARLA generated them or that a statutory exception applies.
"""
import hashlib
import json
import math
from pathlib import Path
import xml.etree.ElementTree as ET

from build import CASE, HERE, POLICIES, RATE, SOURCE, SOURCE_SHA, pose, put, sha

FRAMES = 800
CENTERS = {"divided_reference": -45.0, "divided_opening": 0.0}
OPENING_X = (-10.0, 10.0)
SEGMENTS = ((503, -100.0, 90.0, "median"), (504, -10.0, 20.0, "opening"),
            (505, 10.0, 90.0, "median"))
BRANCH = HERE / "divided-opening"


def lane(ident, kind="driving", mark="solid"):
    return (f'<lane id="{ident}" type="{kind}" level="false"><link>'
            f'<predecessor id="{ident}"/><successor id="{ident}"/></link>'
            f'<width sOffset="0" a="4" b="0" c="0" d="0"/>'
            f'<roadMark sOffset="0" type="{mark}" color="white" width="0.12"/></lane>')


def road():
    pieces = []
    for ident, x, length, kind in SEGMENTS:
        predecessor = f'<predecessor elementType="road" elementId="{ident-1}" contactPoint="end"/>' if ident != 503 else ""
        successor = f'<successor elementType="road" elementId="{ident+1}" contactPoint="start"/>' if ident != 505 else ""
        pieces.append(
            f'<road id="{ident}" name="divided-highway-{kind}" length="{length}" junction="-1">'
            f'<link>{predecessor}{successor}</link>'
            '<type s="0" type="town"><speed max="25" unit="mph"/></type>'
            f'<planView><geometry s="0" x="{x}" y="0" hdg="0" length="{length}"><line/></geometry></planView>'
            '<elevationProfile><elevation s="0" a="0" b="0" c="0" d="0"/></elevationProfile>'
            '<lanes><laneSection s="0"><left>'
            + lane(1, "driving" if kind == "opening" else "median",
                   "broken" if kind == "opening" else "solid")
            + ''.join(lane(i) for i in (2, 3, 4))
            + '</left><center><lane id="0" type="none" level="false"/></center><right>'
            + ''.join(lane(i) for i in (-1, -2, -3))
            + '</right></laneSection></lanes><objects/><signals/></road>')
    return ('<?xml version="1.0" encoding="UTF-8"?><OpenDRIVE>'
            '<header revMajor="1" revMinor="4" name="C111662 divided-highway opening request" '
            'version="1" date="2026-11-08" north="20" south="-20" east="100" west="-100" vendor="worker"/>'
            + ''.join(pieces) + '</OpenDRIVE>\n')


def tracks(suffix, candidate):
    center = CENTERS[suffix]
    speed, _, dwell = POLICIES[candidate]
    output = []
    for frame in range(FRAMES):
        t = frame / RATE
        x, y, heading, velocity, phase = pose(t, center, speed, dwell)
        output.append({
            "frame": frame, "time_s": t,
            "requested_ego_xyz_m": [round(x, 6), round(y, 6), 0],
            "requested_heading_rad": round(heading, 9),
            "requested_speed_mps": round(velocity, 6),
            "requested_phase": phase, "requested_turn_center_x_m": center,
            "authored_opening_x_m": list(OPENING_X),
            "authored_divided_highway": True,
            "median_open_at_crossing": suffix == "divided_opening",
            "district_designation_verified": False,
            "opening_exception_legally_verified": False,
            "original_native_observed": False, "legal_verdict": None})
    return output


def build():
    if sha(SOURCE) != SOURCE_SHA:
        raise ValueError("Frozen assignment changed")
    source = json.loads(SOURCE.read_text())
    if "on a divided highway where an appropriate opening or crossing place exists" not in source["law_record"]["text"]:
        raise ValueError("Statutory opening clause changed")
    entries = []
    for suffix in CENTERS:
        for candidate in POLICIES:
            bundle = BRANCH / "drafts" / suffix / candidate
            bundle.mkdir(parents=True, exist_ok=True)
            (bundle / "assignment-source.json").write_bytes(SOURCE.read_bytes())
            (bundle / "divided-highway.xodr").write_text(road())
            track = bundle / "requested-tracks.jsonl"
            track.write_text(''.join(json.dumps(row, sort_keys=True) + '\n'
                                     for row in tracks(suffix, candidate)))
            speed, camera, dwell = POLICIES[candidate]
            config = {
                "format": "c111662-4033-divided-opening-request-v1",
                "assignment_id": CASE.name, "assignment_sha256": SOURCE_SHA,
                "case_id": CASE.name + "__" + suffix, "candidate_id": candidate,
                "source_text": source["law_record"]["text"],
                "road_sha256": sha(bundle / "divided-highway.xodr"),
                "tracks_sha256": sha(track), "frames": FRAMES, "rate_hz": RATE,
                "requested_turn_center_x_m": CENTERS[suffix],
                "requested_approach_speed_mps": speed,
                "camera_policy": camera, "pre_turn_dwell_s": dwell,
                "ego_blueprint": "vehicle.tesla.model3",
                "status": "unselected_native_request",
                "original_native_observed": False, "legal_verdict": None}
            put(bundle / "config.json", config)
            entries.append({"case_id": config["case_id"], "candidate_id": candidate,
                            "config_sha256": sha(bundle / "config.json")})
    manifest = {"format": "c111662-4033-divided-opening-manifest-v1",
                "assignment_id": CASE.name, "assignment_sha256": SOURCE_SHA,
                "status": "draft_not_selected", "entries": entries,
                "original_native_observed": False, "delivery_ready": False}
    put(BRANCH / "manifest.json", manifest)
    return manifest


def check(bundle):
    bundle = Path(bundle)
    cfg = json.loads((bundle / "config.json").read_text())
    suffix, candidate = cfg["case_id"].split("__")[-1], cfg["candidate_id"]
    if suffix not in CENTERS or candidate not in POLICIES:
        raise ValueError("Unknown divided branch candidate")
    source = json.loads(SOURCE.read_text())
    speed, camera, dwell = POLICIES[candidate]
    if ((bundle / "assignment-source.json").read_bytes() != SOURCE.read_bytes() or
            sha(SOURCE) != SOURCE_SHA or cfg["assignment_id"] != CASE.name or
            cfg["assignment_sha256"] != SOURCE_SHA or
            cfg["source_text"] != source["law_record"]["text"] or
            cfg["requested_turn_center_x_m"] != CENTERS[suffix] or
            cfg["requested_approach_speed_mps"] != speed or
            cfg["camera_policy"] != camera or cfg["pre_turn_dwell_s"] != dwell or
            cfg["frames"] != FRAMES or cfg["rate_hz"] != RATE or
            cfg["status"] != "unselected_native_request" or
            cfg["original_native_observed"] is not False or cfg["legal_verdict"] is not None):
        raise ValueError("Source-bound divided branch config changed")
    path = bundle / "divided-highway.xodr"
    if path.read_text() != road() or cfg["road_sha256"] != sha(path):
        raise ValueError("Divided-highway geometry changed")
    xml = ET.parse(path).getroot()
    pieces = {int(item.attrib["id"]): item for item in xml.findall("road")}
    if set(pieces) != {503, 504, 505}:
        raise ValueError("Median and opening segments changed")
    for ident, _, _, kind in SEGMENTS:
        lanes = {int(item.attrib["id"]): item for item in
                 pieces[ident].findall("./lanes/laneSection/left/lane")}
        if (set(lanes) != {1, 2, 3, 4} or
                lanes[1].attrib["type"] != ("driving" if kind == "opening" else "median") or
                lanes[1].find("roadMark").attrib["type"] !=
                ("broken" if kind == "opening" else "solid")):
            raise ValueError("Authored median opening changed")
    track = bundle / "requested-tracks.jsonl"
    observed = [json.loads(line) for line in track.read_text().splitlines()]
    if cfg["tracks_sha256"] != sha(track) or observed != tracks(suffix, candidate):
        raise ValueError("Divided branch tracks changed")
    return {"case_id": cfg["case_id"], "candidate_id": candidate,
            "frames": FRAMES, "original_native_observed": False,
            "delivery_ready": False}


def measure(bundle):
    check(bundle)
    cfg = json.loads((Path(bundle) / "config.json").read_text())
    rows = [json.loads(line) for line in (Path(bundle) / "requested-tracks.jsonl").read_text().splitlines()]
    turn = [row for row in rows if row["requested_phase"] == "u_turn"]
    crossing = next((row for row in turn if row["requested_ego_xyz_m"][1] >= 0), None)
    if crossing is None or max(row["requested_heading_rad"] for row in turn) < math.pi - .04:
        raise ValueError("Requested turn does not cross median and reverse")
    x = crossing["requested_ego_xyz_m"][0]
    open_at_crossing = OPENING_X[0] <= x <= OPENING_X[1]
    if open_at_crossing != cfg["case_id"].endswith("__divided_opening"):
        raise ValueError("Opening comparison location changed")
    return {"format": "c111662-4033-divided-opening-measurement-v1",
            "case_id": cfg["case_id"], "candidate_id": cfg["candidate_id"],
            "crossing_x_m": x, "crossing_frame": crossing["frame"],
            "crossing_in_authored_opening": open_at_crossing,
            "median_road_ids": [503, 505], "opening_road_id": 504,
            "synthetic_request_only": True, "original_native_observed": False,
            "legal_verdict": None, "delivery_ready": False}


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", type=Path)
    args = parser.parse_args()
    print(json.dumps(check(args.check) if args.check else
                     {"constructed": len(build()["entries"])}))
