"""Source-bound activation classification for NRS 484B.267(2)(a).

This classifies observed branches; it never decides reasonable and proper speed
or legal compliance. A visibility claim needs a camera pixel source, not a flag.
"""
import argparse
import hashlib
import json
from pathlib import Path


LAW_SOURCE = "NRS 484B.267(2)(a); with 484B.267(4)"
BRANCHES = {
    "already_moving": "moving in any direction",
    "visible_vehicle_movement": "A movement of the vehicle",
    "visible_driver_hand_signal": "The use of hand signals by the driver of the vehicle",
    "officer_directed": "except when otherwise directed by a law enforcement officer",
}


def require(ok, message):
    if not ok:
        raise ValueError(message)


def classify(evidence):
    require(evidence.get("source_kind") == "original_native_observation",
            "Original Native source required")
    require(evidence.get("subject_approach_source_id"), "Subject approach source missing")
    require(evidence.get("authorized_vehicle_source_id")
            and evidence.get("vehicle_kind") in
            ("authorized_emergency_vehicle", "official_regulatory_vehicle"),
            "Qualified vehicle source missing")
    require(evidence.get("flashing_equipment_source_id")
            and evidence.get("flashing_pixel_source_id")
            and evidence.get("flashing_qualification_source_id"),
            "Qualifying flashing light sources missing")
    require(evidence.get("officer_direction_source_id"),
            "Officer direction source missing")
    require(evidence.get("road_context_source_id")
            and evidence.get("weather_context_source_id"),
            "Reasonable speed context source missing")
    require(type(evidence.get("already_moving")) is bool, "Movement state unknown")
    require(type(evidence.get("visible_vehicle_movement")) is bool
            and type(evidence.get("visible_driver_hand_signal")) is bool,
            "Visible preparation alternatives unknown")
    require(type(evidence.get("officer_directed")) is bool,
            "Officer exception state unknown")
    if evidence["visible_vehicle_movement"]:
        require(evidence.get("movement_pixel_source_id"),
                "Visible vehicle movement pixel source missing")
    if evidence["visible_driver_hand_signal"]:
        require(evidence.get("hand_signal_pixel_source_id")
                and evidence.get("hand_signal_actor_source_id"),
                "Visible driver hand signal source missing")
    active = [name for name in ("already_moving", "visible_vehicle_movement",
                               "visible_driver_hand_signal") if evidence[name]]
    require(active, "No observed moving or visible preparing-to-move branch")
    if evidence["officer_directed"]:
        require(evidence.get("officer_instruction_source_id"),
                "Officer instruction source missing")
        disposition = "officer_direction_exception_review"
    else:
        disposition = "speed_decrease_measurement_required"
    return {"format": "c405647-source-bound-branch-classification-v1",
            "law_source": LAW_SOURCE,
            "observed_activation_branches": active,
            "source_quotes": {name: BRANCHES[name] for name in active},
            "officer_exception": evidence["officer_directed"],
            "disposition": disposition,
            "reasonable_and_proper_legally_determined": False,
            "legal_outcome_claimed": False}


def classify_file(path):
    source = Path(path)
    result = classify(json.loads(source.read_text()))
    result["source_path"] = str(source)
    result["source_sha256"] = hashlib.sha256(source.read_bytes()).hexdigest()
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence", required=True)
    args = parser.parse_args()
    print(json.dumps(classify_file(args.evidence), indent=2, sort_keys=True))
