"""Review and hash the original source packet for an LVMC lamp capture.

The packet requests a construction. It cannot itself prove realized lamp output,
visibility, covered status, or a legal conclusion.
"""

import argparse
from datetime import datetime
import hashlib
import json
import math
from pathlib import Path


ASSIGNMENT = "testing__C230286__LVMC-11-38-120-B__motorcycle_or_moped_operator"
SOURCE_NAMES = (
    "map_opendrive", "vehicle_coverage", "road_sidewalk_geometry",
    "astronomical_times", "light_atmosphere", "discernibility_protocol",
    "headlamp_photometry", "tail_lamp_photometry",
)
REQUESTS = {
    "coverage_request": {"covered_motorcycle", "trail_ride_exclusion_probe",
                         "enclosed_three_wheel_exclusion_probe"},
    "illumination_request": {"night", "day_clear", "day_lowlight", "day_atmosphere"},
    "motion_request": {"moving", "stopped"},
    "lit_state_request": {"both_lit", "both_off", "head_off", "tail_off"},
    "calibrated_lamp_request": {
        "white_300_red_500", "white_299_red_500", "white_301_red_500",
        "white_300_red_499", "white_300_red_501", "nonwhite_300_red_500",
        "white_300_nonred_500",
    },
    "timing_request": {"night", "day", "sunset_plus_29min", "sunset_plus_30min",
                       "sunset_plus_31min", "sunrise_minus_31min",
                       "sunrise_minus_30min", "sunrise_minus_29min"},
}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _number(value, label):
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValueError(label + " must be a finite original number")
    return float(value)


def verify(packet_path, *, diagnostic_fixture=False):
    packet_path = Path(packet_path)
    packet = json.loads(packet_path.read_text(encoding="utf-8"))
    if packet.get("assignment_id") != ASSIGNMENT:
        raise ValueError("source packet assignment mismatch")
    case_id = packet.get("case_id")
    if not isinstance(case_id, str) or not case_id.startswith(ASSIGNMENT + "__"):
        raise ValueError("source packet exact case mismatch")
    if packet.get("source_kind") != ("diagnostic_fixture" if diagnostic_fixture else "original_reviewed"):
        raise ValueError("reviewed original source packet required")
    refs = packet.get("source_refs")
    if not isinstance(refs, dict) or set(refs) != set(SOURCE_NAMES):
        raise ValueError("all independent original source references required")
    for name, ref in refs.items():
        if not isinstance(ref, dict) or set(ref) != {"path", "sha256", "reviewed_by", "method"}:
            raise ValueError("incomplete original source reference: " + name)
        path = Path(ref["path"])
        if path.is_absolute() or ".." in path.parts or len(path.parts) != 1:
            raise ValueError("source reference must be a sibling file: " + name)
        original = packet_path.parent / path
        if not original.is_file() or sha(original) != ref["sha256"]:
            raise ValueError("missing or changed original source: " + name)
        if not ref["reviewed_by"] or not ref["method"]:
            raise ValueError("source review provenance missing: " + name)
    scene = packet.get("scene")
    if not isinstance(scene, dict):
        raise ValueError("source-grounded scene required")
    for key in ("cell_id", "law_id", "actor", "map_name", "vehicle_blueprint",
                "route", "sidewalk", "local_datetime", "sunset_local", "sunrise_local",
                *REQUESTS):
        if key not in scene:
            raise ValueError("source-grounded scene field missing: " + key)
    if (scene["cell_id"], scene["law_id"], scene["actor"]) != (
            "C230286", "LVMC-11-38-120-B", "motorcycle_or_moped_operator"):
        raise ValueError("source-grounded scene identity mismatch")
    if scene["route"].get("surface") != "roadway" or scene["sidewalk"].get("surface") != "sidewalk":
        raise ValueError("roadway travel and separate sidewalk geometry required")
    if scene["route"].get("sidewalk_relation") != "adjacent_separate":
        raise ValueError("fixed sidewalk relation changed")
    if not scene["route"].get("waypoints") or not scene["sidewalk"].get("polygon"):
        raise ValueError("source surveyed route and sidewalk polygon required")
    if not scene["map_name"] or not scene["vehicle_blueprint"]:
        raise ValueError("reviewed map and motorcycle blueprint required")
    for key, allowed in REQUESTS.items():
        if scene[key] not in allowed:
            raise ValueError("invalid controlled request: " + key)
    if scene["coverage_request"] != "covered_motorcycle" and scene["vehicle_blueprint"] == "":
        raise ValueError("coverage control vehicle required")
    if not all(isinstance(scene[x], str) and scene[x] for x in (
            "local_datetime", "sunset_local", "sunrise_local")):
        raise ValueError("original astronomical timing required")
    try:
        astronomical_source = json.loads((packet_path.parent / refs["astronomical_times"]["path"])
                                        .read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise ValueError("readable original astronomical source required") from error
    if any(astronomical_source.get(key) != scene[key] for key in
           ("local_datetime", "sunset_local", "sunrise_local")):
        raise ValueError("astronomical source differs from requested scene")
    try:
        local_time = datetime.fromisoformat(scene["local_datetime"])
        sunset = datetime.fromisoformat(scene["sunset_local"])
        sunrise = datetime.fromisoformat(scene["sunrise_local"])
        if any(value.tzinfo is None for value in (local_time, sunset, sunrise)):
            raise ValueError("timezone-aware original astronomical timing required")
        since_sunset = (local_time - sunset).total_seconds() / 60
        before_sunrise = (sunrise - local_time).total_seconds() / 60
    except (TypeError, ValueError) as error:
        raise ValueError("valid original astronomical timing required") from error
    timing = scene["timing_request"]
    if timing.startswith("sunset_plus_"):
        expected = int(timing.removeprefix("sunset_plus_").removesuffix("min"))
        if abs(since_sunset - expected) > 0.001:
            raise ValueError("sunset offset request differs from source time")
    if timing.startswith("sunrise_minus_"):
        expected = int(timing.removeprefix("sunrise_minus_").removesuffix("min"))
        if abs(before_sunrise - expected) > 0.001:
            raise ValueError("sunrise offset request differs from source time")
    if _number(scene.get("duration_s"), "duration_s") <= 0 or scene.get("rate_hz") != 20:
        raise ValueError("positive duration and 20 Hz capture required")
    if _number(scene.get("requested_speed_mps"), "requested_speed_mps") < 0:
        raise ValueError("negative requested speed")
    if _number(scene.get("discernibility_request_ft"), "discernibility_request_ft") < 0:
        raise ValueError("negative discernibility request")
    return {"assignment_id": ASSIGNMENT, "case_id": case_id,
            "packet_sha256": sha(packet_path),
            "source_hashes": {name: ref["sha256"] for name, ref in refs.items()},
            "requested_controls": {**{name: scene[name] for name in REQUESTS},
                                   "discernibility_request_ft": scene["discernibility_request_ft"]},
            "astronomical_offsets_minutes": {"since_sunset": since_sunset,
                                             "before_sunrise": before_sunrise},
            "physical_acceptance": "unverified"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--packet", required=True)
    parser.add_argument("--diagnostic-fixture", action="store_true")
    args = parser.parse_args()
    print(json.dumps(verify(args.packet, diagnostic_fixture=args.diagnostic_fixture), sort_keys=True))


if __name__ == "__main__":
    main()
