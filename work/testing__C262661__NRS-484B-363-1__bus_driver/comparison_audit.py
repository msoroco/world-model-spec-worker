"""Independent source-bound comparison checks for exact school-zone probes."""

import argparse
import json
from datetime import datetime, timedelta
from pathlib import Path

from school_scene_construction import ROOT, SOURCES
from school_zone_observations import measure

CHANGES = {
    "below_versus_at_15_mph": ("speed", ()),
    "at_versus_above_15_mph": ("speed", ()),
    "school_not_in_session": ("session", ("school_calendar",)),
    "half_hour_after_operation": ("clock", ("civil_date_time",)),
    "half_hour_before_next_operation": ("clock", ("civil_date_time",)),
    "class_hours_beacon_flashing": ("lamps", ("beacon_lamp_history",)),
    "nonbeacon_sign_time_indication": ("sign", ("sign_active_period",)),
    "two_yellow_light_definition": ("lamp_count", ("beacon_lamp_configuration",)),
    "alternating_flash_definition": ("alternation", ("beacon_lamp_configuration", "beacon_lamp_history")),
    "designated_zone_boundary": ("zone", ()),
    "children_presence_is_not_independent_exception": ("children", ("children_locations",)),
    "bus_versus_other_motor_vehicle": ("vehicle", ("bus_blueprint",)),
}


def require(ok, message):
    if not ok:
        raise ValueError(message)


def _read(folder, case_id):
    folder = Path(folder)
    result = measure(case_id, folder / "context.json", folder / "original-trace.jsonl",
                     folder / "receipt.json")
    context = json.loads((folder / "context.json").read_text())
    rows = [json.loads(line) for line in (folder / "original-trace.jsonl").read_text().splitlines()]
    require(len(rows) >= 2 and context.get("case_id") == case_id,
            "original exact comparison capture missing")
    for name in SOURCES:
        digest = context.get(name + "_source_sha256")
        require(isinstance(digest, str) and len(digest) == 64 and
                all(c in "0123456789abcdef" for c in digest),
                "original school source hash absent: " + name)
    return context, rows, result


def audit(comparison_id, left_folder, right_folder):
    plan = json.loads((ROOT / "case-plan.json").read_text())
    matched = [row for row in plan["comparisons"] if row["comparison_id"] == comparison_id]
    require(len(matched) == 1 and comparison_id in CHANGES,
            "unknown exact school-zone comparison")
    case_ids = matched[0]["case_ids"]
    a, rows_a, measured_a = _read(left_folder, case_ids[0])
    b, rows_b, measured_b = _read(right_folder, case_ids[1])
    variable, changed_sources = CHANGES[comparison_id]
    require(a["map_sha256"] == b["map_sha256"] and
            a.get("zone_polygon_xy_m") == b.get("zone_polygon_xy_m") and
            a.get("route_xy_m") == b.get("route_xy_m"),
            "comparison map, designated zone or route changed")
    for name in set(SOURCES) - set(changed_sources):
        require(a[name + "_source_sha256"] == b[name + "_source_sha256"],
                "fixed school source changed: " + name)
    if changed_sources:
        require(any(a[name + "_source_sha256"] != b[name + "_source_sha256"]
                    for name in changed_sources),
                "declared changed original source has identical bytes")
    if variable == "speed":
        values = [item["maximum_observed_inside_zone_mph"] for item in
                  (measured_a, measured_b)]
        require(all(v is not None for v in values) and values[0] < values[1],
                "actual bus speed comparison order not observed")
    elif variable == "session":
        require(a["school_in_session_today"] != b["school_in_session_today"],
                "independent session contrast absent")
    elif variable == "clock":
        require(a["local_datetime"] != b["local_datetime"],
                "independent clock contrast absent")
        instant = datetime.fromisoformat(b["local_datetime"])
        require(instant.tzinfo is not None and instant.utcoffset() is not None,
                "offset-aware school clock required")
        if comparison_id == "half_hour_after_operation":
            end = datetime.fromisoformat(b["operation_end_local"])
            require(end + timedelta(minutes=30) <= instant < end + timedelta(minutes=60),
                    "after-operation half-hour boundary absent")
        else:
            next_start = datetime.fromisoformat(b["next_operation_start_local"])
            require(next_start - timedelta(minutes=60) < instant <=
                    next_start - timedelta(minutes=30),
                    "before-operation half-hour boundary absent")
    elif variable == "lamps":
        require([row["beacon_yellow_lights_lit"] for row in rows_a] !=
                [row["beacon_yellow_lights_lit"] for row in rows_b],
                "actual beacon flash contrast absent")
    elif variable == "sign":
        require([row["sign_limit_active"] for row in rows_a] !=
                [row["sign_limit_active"] for row in rows_b],
                "actual nonbeacon sign contrast absent")
    elif variable == "lamp_count":
        require(len(rows_a[0]["beacon_yellow_lights_lit"]) !=
                len(rows_b[0]["beacon_yellow_lights_lit"]),
                "actual beacon lamp-count contrast absent")
    elif variable == "alternation":
        require([row["beacon_yellow_lights_lit"] for row in rows_a] !=
                [row["beacon_yellow_lights_lit"] for row in rows_b],
                "actual alternating-lamp contrast absent")
    elif variable == "zone":
        require([row["inside_designated_zone"] for row in rows_a] !=
                [row["inside_designated_zone"] for row in rows_b],
                "actual zone-boundary contrast absent")
    elif variable == "children":
        require([row["children_actor_ids"] for row in rows_a] !=
                [row["children_actor_ids"] for row in rows_b],
                "actual children contrast absent")
    elif variable == "vehicle":
        require(isinstance(a.get("vehicle_blueprint"), str) and
                a["vehicle_blueprint"].startswith("vehicle.") and
                isinstance(b.get("vehicle_blueprint"), str) and
                b["vehicle_blueprint"].startswith("vehicle.") and
                a["vehicle_blueprint"] != b["vehicle_blueprint"],
                "actual bus versus car contrast absent")
    return {"comparison_id": comparison_id, "case_ids": case_ids,
            "source_bindings": [measured_a["source_bindings"], measured_b["source_bindings"]],
            "fixed_sources_checked": sorted(set(SOURCES) - set(changed_sources)),
            "observed_difference": variable, "physical_acceptance": "unverified",
            "legal_judgment": "unresolved"}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--comparison", required=True)
    parser.add_argument("--left", required=True)
    parser.add_argument("--right", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    result = audit(args.comparison, args.left, args.right)
    Path(args.output).write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
