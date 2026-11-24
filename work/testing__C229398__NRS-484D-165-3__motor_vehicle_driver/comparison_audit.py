"""Independent exact-case comparison of saved parked-lamp source evidence."""

import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ASSIGNMENT = ROOT.name
FIELDS = ("placement", "lighting", "lamps", "attendance", "time_qualifies")
FIXED_SITE_FIELDS = (
    "map_sha256", "map_name", "curb_waypoint_xyz", "road_id", "lane_id",
    "traffic_side", "highway_public_use_source", "shoulder_boundary_source",
    "traveled_boundary_source", "traffic_direction_source", "vehicle_class_source",
    "visibility_station_source", "lamp_installation_source",
    "shoulder_spawn_transform", "traveled_spawn_transform",
    "revelation_station_m", "front_lamp_station_m", "rear_lamp_station_m",
    "installed_lamp_positions", "camera_transforms")


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def source(attempt, relative):
    root = Path(attempt).resolve()
    path = (root / relative).resolve()
    require(path.is_relative_to(root) and path.is_file(), "missing contained comparison source: " + relative)
    return path


def fixed_signature(site):
    selected = {key: site.get(key) for key in FIXED_SITE_FIELDS}
    return hashlib.sha256(json.dumps(selected, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def member(report_path, attempt, expected_id, expected, diagnostic):
    report_path = Path(report_path)
    report = json.loads(report_path.read_text())
    require(report.get("case_id") == expected_id and report.get("analysis_complete") is True,
            "comparison report case or analysis incomplete")
    require(report.get("diagnostic_fixture") is diagnostic,
            "comparison provenance differs from selected mode")
    measured = report.get("saved_measurement", {})
    require(measured.get("case_id") == expected_id and measured.get("spec") ==
            {key: expected[key] for key in FIELDS if key != "time_qualifies"},
            "comparison measurement case or conditions differ")
    require(measured.get("time_qualifies") is expected["time_qualifies"],
            "comparison referenced-time condition differs")
    require(measured.get("map_sha256") and measured.get("fixed_site_signature") and
            measured.get("site_source_sha256"), "comparison fixed site source missing")
    names = ("capture/site_packet.json", "capture/original_history.jsonl")
    for name in names:
        actual = sha(source(attempt, name))
        for key in ("parked_position", "referenced_time", "revelation_1000ft",
                    "lamp_views_500ft", "traffic_side_installation"):
            require(report.get("measurements", {}).get(key, {}).get("sources", {}).get(name) == actual,
                    "comparison measurement source hash differs: " + name)
    packet = json.loads(source(attempt, "capture/site_packet.json").read_text())
    require(packet.get("case_id") == expected_id and packet.get("map_sha256") == measured["map_sha256"] and
            packet.get("site_source_sha256") == measured["site_source_sha256"],
            "comparison source packet differs")
    if diagnostic:
        fixture = json.loads(source(attempt, "diagnostic-source.json").read_text())
        require(fixture.get("diagnostic_fixture") is True and fixture.get("case_id") == expected_id and
                fixture.get("measurement") == measured, "diagnostic comparison source differs")
    else:
        require(packet.get("site_source_sha256") == sha(source(attempt, "capture/site_source.json")),
                "independent site source hash differs")
        site = json.loads(source(attempt, "capture/site_packet.json").read_text())
        evidence = json.loads(source(attempt, "capture/site_source.json").read_text())
        require(all(site.get(key) == evidence.get(key) for key in FIXED_SITE_FIELDS),
                "independent fixed site evidence differs")
        require(measured["fixed_site_signature"] == fixed_signature(site),
                "comparison fixed site signature differs")
        require(site.get("time_qualifies") is expected["time_qualifies"] and
                site.get("lighting_assessment") == expected["lighting"],
                "comparison original site condition differs")
        rows = source(attempt, "capture/original_history.jsonl").read_text().splitlines()
        require(len(rows) == 900 and measured.get("original_frame_count") == 900 and
                len(measured.get("one_hz_original_samples", [])) == 45,
                "comparison original parked interval incomplete")
        for index, line in enumerate(rows):
            frame = json.loads(line)
            require(frame.get("frame_index") == index and
                    abs(frame.get("time_s", -1) - index / 20) <= 0.002 and
                    frame.get("map_sha256") == measured["map_sha256"] and
                    frame.get("vehicle_alive") is True and
                    frame.get("vehicle_role") == "motor_vehicle_driver" and
                    frame.get("placement") == expected["placement"] and
                    frame.get("attendance") == expected["attendance"] and
                    frame.get("lighting_assessment") == expected["lighting"] and
                    frame.get("time_qualifies") is expected["time_qualifies"] and
                    frame.get("front_lamp_state") == expected["lamps"] and
                    frame.get("rear_lamp_state") == expected["lamps"] and
                    frame.get("parking_brake") is True and
                    type(frame.get("speed_mps")) in (int, float) and
                    0 <= frame["speed_mps"] <= 0.25,
                    "comparison original frame condition differs")
    return measured, {name: sha(source(attempt, name)) for name in names}


def audit(comparison_id, left_report, right_report, left_attempt, right_attempt,
          *, diagnostic=False, plan_path=None):
    plan_path = Path(plan_path or ROOT / "case-plan.json")
    plan = json.loads(plan_path.read_text())
    require(plan.get("assignment_id") == ASSIGNMENT, "comparison plan assignment differs")
    matches = [item for item in plan["comparisons"] if item["comparison_id"] == comparison_id]
    require(len(matches) == 1, "unknown or duplicate comparison ID")
    comparison = matches[0]
    ids = comparison["case_ids"]
    require(len(ids) == 2 and len(set(ids)) == 2, "comparison needs exact two members")
    changed = comparison["changed_fields"]
    require(len(changed) == 1 and changed[0] in FIELDS, "comparison change declaration invalid")
    cases = {item["case_id"]: item for item in plan["cases"]}
    require(all(case_id in cases for case_id in ids), "comparison member missing from plan")
    expected = [cases[case_id]["intended_conditions"] for case_id in ids]
    for field in FIELDS:
        values = [case[field] for case in expected]
        require((values[0] != values[1]) == (field in changed),
                "plan has undeclared or absent difference: " + field)
    left, left_sources = member(left_report, left_attempt, ids[0], expected[0], diagnostic)
    right, right_sources = member(right_report, right_attempt, ids[1], expected[1], diagnostic)
    for key in ("map_sha256", "fixed_site_signature"):
        require(left[key] == right[key], "comparison fixed site changed: " + key)
    if diagnostic and changed[0] not in ("lighting", "time_qualifies"):
        require(left["site_source_sha256"] == right["site_source_sha256"],
                "comparison site source changed without declared lighting/time difference")
    return {"format": "c229398-independent-comparison-audit", "comparison_id": comparison_id,
            "case_ids": ids, "changed_fields": changed, "fixed_site_verified": True,
            "source_hashes": {ids[0]: left_sources, ids[1]: right_sources},
            "report_sha256": {ids[0]: sha(left_report), ids[1]: sha(right_report)},
            "plan_sha256": sha(plan_path), "diagnostic_fixture": diagnostic,
            "physical_acceptance_claimed": False, "legal_verdict": None}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--comparison", required=True)
    parser.add_argument("--left-report", required=True)
    parser.add_argument("--right-report", required=True)
    parser.add_argument("--left-attempt", required=True)
    parser.add_argument("--right-attempt", required=True)
    parser.add_argument("--plan", default=str(ROOT / "case-plan.json"))
    parser.add_argument("--output", required=True)
    parser.add_argument("--diagnostic", action="store_true")
    args = parser.parse_args()
    result = audit(args.comparison, args.left_report, args.right_report,
                   args.left_attempt, args.right_attempt, diagnostic=args.diagnostic,
                   plan_path=args.plan)
    Path(args.output).write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
