"""Source-bound heavy vehicle speed, school-crossing-zone and device observations for NRS 484B.363(1)."""

import argparse
import hashlib
import json
import math
from pathlib import Path

ASSIGNMENT_ID = "testing__C255456__NRS-484B-363-2__heavy_vehicle_driver"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def measure(case_id, context_path, trace_path, receipt_path):
    if not case_id.startswith(ASSIGNMENT_ID + "__"):
        raise ValueError("exact assignment case required")
    receipt = json.loads(Path(receipt_path).read_text(encoding="utf-8"))
    if (receipt.get("assignment_id"), receipt.get("case_id")) != (ASSIGNMENT_ID, case_id):
        raise ValueError("original source receipt identity mismatch")
    if receipt.get("diagnostic_fixture") or receipt.get("source_kind") != "original_native_capture":
        raise ValueError("original Native capture required")
    if receipt.get("context_sha256") != sha(context_path) or receipt.get("trace_sha256") != sha(trace_path):
        raise ValueError("original source bytes changed")
    context = json.loads(Path(context_path).read_text(encoding="utf-8"))
    if context.get("case_id") != case_id or not isinstance(context.get("map_sha256"), str) or len(context["map_sha256"]) != 64:
        raise ValueError("exact source map context required")
    for key in ("zone_designation_source", "zone_boundaries_source", "school_property_source",
                "heavy_route_source", "heavy_blueprint_source", "driver_identity_source", "children_locations_source",
                "civil_date_time_source", "school_calendar_source", "operation_hours_source",
                "class_hours_source", "beacon_designation_source", "beacon_operability_source",
                "beacon_lamp_configuration_source", "beacon_lamp_history_source", "sign_active_period_source"):
        if not context.get(key):
            raise ValueError("original context source missing: " + key)
    for key in ("local_datetime", "operation_end_local", "next_operation_start_local",
                "class_start_local", "class_end_local"):
        if not isinstance(context.get(key), str) or not context[key]:
            raise ValueError("independent original school timing missing: " + key)
    if type(context.get("school_in_session_today")) is not bool or type(context.get("operational_beacon_designation")) is not bool:
        raise ValueError("independent session and beacon designation facts required")
    rows = [json.loads(line) for line in Path(trace_path).read_text(encoding="utf-8").splitlines() if line]
    if len(rows) < 2 or len(rows) != receipt.get("frame_count") or receipt.get("fps") != 20:
        raise ValueError("original 20 Hz frame count mismatch")
    observations = []
    for index, row in enumerate(rows):
        if row.get("frame") != index or not isinstance(row.get("time_s"), (int, float)) or abs(row["time_s"] - index / 20) > .002:
            raise ValueError("original frame cadence mismatch")
        speed = row.get("heavy_speed_mps")
        if not isinstance(speed, (int, float)) or not math.isfinite(speed) or speed < 0:
            raise ValueError("original heavy vehicle speed required")
        if type(row.get("inside_designated_zone")) is not bool:
            raise ValueError("original zone membership required")
        lights = row.get("beacon_yellow_lights_lit")
        if not isinstance(lights, list) or any(type(x) is not bool for x in lights):
            raise ValueError("independent original yellow lamp states required")
        if type(row.get("sign_limit_active")) is not bool:
            raise ValueError("original sign-active observation required")
        children = row.get("children_actor_ids")
        if not isinstance(children, list) or any(not isinstance(x, str) or not x for x in children):
            raise ValueError("original children inventory required")
        observations.append({"frame": index, "time_s": row["time_s"],
                             "heavy_speed_mps": speed, "heavy_speed_mph": speed * 2.2369362921,
                             "inside_designated_zone": row["inside_designated_zone"],
                             "beacon_yellow_lights_lit": lights,
                             "sign_limit_active": row["sign_limit_active"],
                             "children_actor_ids": children})
    return {"assignment_id": ASSIGNMENT_ID, "case_id": case_id,
            "source_bindings": {"context_sha256": sha(context_path), "trace_sha256": sha(trace_path),
                                "receipt_sha256": sha(receipt_path), "native_map_sha256": context["map_sha256"]},
            "school_in_session_today_source_fact": context["school_in_session_today"],
            "operational_beacon_designation_source_fact": context["operational_beacon_designation"],
            "school_timing_source_facts": {k: context[k] for k in ("local_datetime", "operation_end_local",
                                    "next_operation_start_local", "class_start_local", "class_end_local")},
            "twenty_five_mph_reference_only": 15, "half_hour_reference_minutes_only": 30,
            "maximum_observed_inside_zone_mph": max((x["heavy_speed_mph"] for x in observations if x["inside_designated_zone"]), default=None),
            "observations": observations, "exception_judgment": "unresolved",
            "beacon_definition_judgment": "unresolved", "speed_rule_judgment": "unresolved",
            "physical_acceptance": "unverified"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("case", "context", "trace", "receipt", "output"):
        parser.add_argument("--" + name, required=True)
    args = parser.parse_args()
    result = measure(args.case, args.context, args.trace, args.receipt)
    Path(args.output).write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
