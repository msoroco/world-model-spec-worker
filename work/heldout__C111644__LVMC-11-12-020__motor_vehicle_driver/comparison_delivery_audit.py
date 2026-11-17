"""Audit declared turn-course comparisons from retained original sources."""

import argparse
import hashlib
import json
from pathlib import Path

from indication_form_audit import audit as audit_forms
from turn_marking import audit_saved_turn_route_response


ROUTE_FORMS = {
    "marker_route_response": "marker",
    "button_route_response": "button",
    "other_indication_route_response": "other_indication",
}


def audit_course_deviation(attempts):
    if len(attempts) != 2:
        raise ValueError("Course comparison requires exactly two attempts")
    sources = []
    for attempt in map(Path, attempts):
        config = json.loads((attempt / "config.json").read_text())
        receipt = json.loads((attempt / "turn_source_receipt.json").read_text())
        if config["selected_case_id"] != receipt["case_id"]:
            raise ValueError("Course comparison source selected another case")
        hashes = receipt["source_sha256"]
        for name in ("turn_indication_original.json", "turn_route_plan.json",
                     "turn_body_original.jsonl"):
            source = attempt / name
            if not source.is_file() or hashlib.sha256(source.read_bytes()).hexdigest() != hashes.get(name):
                raise ValueError("Missing or changed original course source: " + name)
        indication = json.loads((attempt / "turn_indication_original.json").read_text())
        route = json.loads((attempt / "turn_route_plan.json").read_text())
        sources.append((config, hashes, indication, route))
    left, right = sources
    left_config, left_hashes, left_indication, left_route = left
    right_config, right_hashes, right_indication, right_route = right
    if not (left_config["selected_case_id"].endswith("__course_2m__marker_depart")
            and right_config["selected_case_id"].endswith("__marker_depart")):
        raise ValueError("Course comparison selected another route pair")
    for key in ("law_id", "cell_id", "actor", "rate_hz", "duration_s", "cameras"):
        if left_config[key] != right_config[key]:
            raise ValueError("Course comparison changed fixed condition: " + key)
    if left_indication != right_indication or left_hashes["turn_indication_original.json"] != right_hashes["turn_indication_original.json"]:
        raise ValueError("Course comparison changed original indication")
    if not (left_route["indication_form"] == right_route["indication_form"] == "marker"
            and left_route["route_variant"] == right_route["route_variant"] == "depart"
            and left_route["course_xy_m"] == right_route["course_xy_m"]
            and left_route["target_route_xy_m"][:-1] == right_route["target_route_xy_m"][:-1]
            and left_route["departure_m"] == left_config["course_deviation_setpoint_m"] == 2.0
            and right_route["departure_m"] == 4.0):
        raise ValueError("Course comparison changed fixed route or planned setpoint")
    a, b = left_route["target_route_xy_m"][-1], right_route["target_route_xy_m"][-1]
    if abs(b[0] - a[0] - 2.0) > 1e-6 or abs(b[1] - a[1]) > 1e-6:
        raise ValueError("Course comparison target separation differs")
    return {"comparison_id": "course_deviation_2m_4m",
            "case_ids": [left_config["selected_case_id"], right_config["selected_case_id"]],
            "same_original_indication": True, "planned_target_separation_m": 2.0,
            "original_body_sources_equal": left_hashes["turn_body_original.jsonl"] == right_hashes["turn_body_original.jsonl"],
            "actual_motion_separation_verified": False,
            "physical_acceptance_claimed": False, "legal_acceptance_claimed": False}


def audit_course_sweep(attempts):
    """Check all three authored targets against the same original indication.

    This verifies the requested controller grid and retained sources. Equal
    synthetic body traces do not establish distinct physical trajectories.
    """
    if len(attempts) != 3:
        raise ValueError("Course sweep requires exactly three attempts")
    rows = []
    for attempt, suffix, expected in zip(map(Path, attempts),
                                         ("__course_2m__marker_depart", "__marker_depart",
                                          "__course_6m__marker_depart"), (2.0, 4.0, 6.0)):
        config = json.loads((attempt / "config.json").read_text())
        receipt = json.loads((attempt / "turn_source_receipt.json").read_text())
        if not config["selected_case_id"].endswith(suffix) or receipt["case_id"] != config["selected_case_id"]:
            raise ValueError("Course sweep selected another case or order")
        hashes = receipt["source_sha256"]
        for name in ("turn_indication_original.json", "turn_route_plan.json", "turn_body_original.jsonl"):
            source = attempt / name
            if not source.is_file() or hashlib.sha256(source.read_bytes()).hexdigest() != hashes.get(name):
                raise ValueError("Missing or changed original course source: " + name)
        indication = json.loads((attempt / "turn_indication_original.json").read_text())
        route = json.loads((attempt / "turn_route_plan.json").read_text())
        if route["departure_m"] != expected or ("course_deviation_setpoint_m" in config and
                config["course_deviation_setpoint_m"] != expected):
            raise ValueError("Course sweep changed an authored setpoint")
        rows.append((config, hashes, indication, route))
    fixed = ("law_id", "cell_id", "actor", "rate_hz", "duration_s", "cameras")
    for key in fixed:
        if len({json.dumps(row[0][key], sort_keys=True) for row in rows}) != 1:
            raise ValueError("Course sweep changed fixed condition: " + key)
    if len({json.dumps(row[2], sort_keys=True) for row in rows}) != 1 or len({row[1]["turn_indication_original.json"] for row in rows}) != 1:
        raise ValueError("Course sweep changed original indication")
    routes = [row[3] for row in rows]
    if (any(route["indication_form"] != "marker" or route["route_variant"] != "depart" for route in routes)
            or len({json.dumps(route["course_xy_m"]) for route in routes}) != 1
            or len({json.dumps(route["target_route_xy_m"][:-1]) for route in routes}) != 1):
        raise ValueError("Course sweep changed fixed route")
    endpoints = [route["target_route_xy_m"][-1] for route in routes]
    if any(abs(endpoints[i + 1][0] - endpoints[i][0] - 2.0) > 1e-6 or
           abs(endpoints[i + 1][1] - endpoints[i][1]) > 1e-6 for i in (0, 1)):
        raise ValueError("Course sweep target separation differs")
    return {"comparison_id": "course_deviation_2m_4m_6m",
            "case_ids": [row[0]["selected_case_id"] for row in rows],
            "same_original_indication": True, "setpoints_m": [2.0, 4.0, 6.0],
            "planned_target_separations_m": [2.0, 2.0],
            "original_body_sources_equal": len({row[1]["turn_body_original.jsonl"] for row in rows}) == 1,
            "actual_motion_separation_verified": False,
            "physical_acceptance_claimed": False, "legal_acceptance_claimed": False}


def audit_marker_placement(attempts):
    if len(attempts) != 2:
        raise ValueError("Placement comparison requires two attempts")
    rows = []
    for attempt in map(Path, attempts):
        config = json.loads((attempt / "config.json").read_text())
        receipt = json.loads((attempt / "turn_source_receipt.json").read_text())
        if receipt["case_id"] != config["selected_case_id"]:
            raise ValueError("Placement source selected another case")
        for name in ("turn_indication_original.json", "turn_route_plan.json", "turn_body_original.jsonl"):
            source = attempt / name
            if not source.is_file() or hashlib.sha256(source.read_bytes()).hexdigest() != receipt["source_sha256"].get(name):
                raise ValueError("Missing or changed original placement source: " + name)
        rows.append((config, receipt["source_sha256"],
                     json.loads((attempt / "turn_indication_original.json").read_text()),
                     json.loads((attempt / "turn_route_plan.json").read_text())))
    (base, base_hash, original, route), (shift, shift_hash, derived, shifted_route) = rows
    if (not base["selected_case_id"].endswith("__marker_follow") or
            not shift["selected_case_id"].endswith("__placement_075m__marker_follow")):
        raise ValueError("Placement comparison selected another case or order")
    for key in ("law_id", "cell_id", "actor", "rate_hz", "duration_s", "cameras"):
        if base[key] != shift[key]:
            raise ValueError("Placement comparison changed fixed condition: " + key)
    if route != shifted_route or base_hash["turn_route_plan.json"] != shift_hash["turn_route_plan.json"]:
        raise ValueError("Placement comparison changed fixed route")
    if (base_hash["turn_body_original.jsonl"] != shift_hash["turn_body_original.jsonl"] or
            shift.get("indication_placement_setpoint_m") != 0.75 or
            derived.get("parent_source_sha256") != base_hash["turn_indication_original.json"] or
            derived.get("placement_shift_m") != 0.75):
        raise ValueError("Placement comparison lacks source-bound 0.75 m shift")
    expected = dict(original)
    expected["parent_source_sha256"] = base_hash["turn_indication_original.json"]
    expected["placement_shift_m"] = 0.75
    expected["indications"] = [dict(item, x=item["x"] + 0.75) for item in original["indications"]]
    if derived != expected:
        raise ValueError("Placement comparison changed more than marker x position")
    return {"comparison_id": "marker_placement_0m_075m",
            "case_ids": [base["selected_case_id"], shift["selected_case_id"]],
            "source_bound_placement_shift_m": 0.75,
            "actual_marker_readback_verified": False,
            "physical_acceptance_claimed": False, "legal_acceptance_claimed": False}


def audit(comparison, attempts):
    if comparison in ROUTE_FORMS:
        if len(attempts) != 2:
            raise ValueError("Route comparison requires exactly two attempts")
        form = ROUTE_FORMS[comparison]
        result = audit_saved_turn_route_response(*map(Path, attempts))
        left = json.loads((Path(attempts[0]) / "config.json").read_text())
        right = json.loads((Path(attempts[1]) / "config.json").read_text())
        if (not left["selected_case_id"].endswith("__" + form + "_follow") or
                not right["selected_case_id"].endswith("__" + form + "_depart")):
            raise ValueError("Comparison selected another indication form or route order")
        if not result["comparison_complete"] or not result["source_joined"]:
            raise ValueError("Route comparison lacks original-source join")
        case_ids = [left["selected_case_id"], right["selected_case_id"]]
        findings = result
    elif comparison == "indication_form":
        if len(attempts) != 3:
            raise ValueError("Form comparison requires exactly three attempts")
        findings = audit_forms(attempts)
        if findings["comparison_id"] != comparison or not findings["fixed_conditions_verified"]:
            raise ValueError("Form comparison lacks fixed-condition proof")
        case_ids = findings["case_ids"]
    elif comparison == "course_deviation_2m_4m":
        findings = audit_course_deviation(attempts)
        case_ids = findings["case_ids"]
    elif comparison == "course_deviation_2m_4m_6m":
        findings = audit_course_sweep(attempts)
        case_ids = findings["case_ids"]
    elif comparison == "marker_placement_0m_075m":
        findings = audit_marker_placement(attempts)
        case_ids = findings["case_ids"]
    else:
        raise ValueError("Unknown declared comparison")
    return {"format": "worker-turn-comparison-delivery-audit",
            "comparison_id": comparison, "case_ids": case_ids,
            "fixed_conditions_checked": True,
            "declared_difference_checked": True,
            "findings": findings,
            "diagnostic_fixture": True,
            "municipal_authorization_verified": False,
            "physical_acceptance_claimed": False,
            "legal_acceptance_claimed": False}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--comparison", required=True)
    parser.add_argument("--attempt", type=Path, action="append", required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = audit(args.comparison, args.attempt)
    if args.output:
        args.output.write_text(json.dumps(result, indent=2) + "\n")
    print("comparison_delivery_audit_passed", args.comparison, len(result["case_ids"]))
