"""Independent fixed-condition review of NRS 484B.270(3) case comparisons.

Diagnostic mode exercises the protocol on synthetic CPU attempts. Production
mode additionally requires an independently reviewed original Native source.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
TARGETS = ("road_user_kind", "ego_precedence_request",
           "ego_lane_action_request", "exception_request")


def read(path: Path) -> dict:
    if path.is_symlink() or not path.is_file():
        raise ValueError("comparison original source missing: " + str(path))
    return json.loads(path.read_text())


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _named(values: list[str]) -> dict[str, Path]:
    result = {}
    for value in values:
        key, sep, path = value.partition("=")
        if not sep or key in result:
            raise ValueError("unique case_id=path argument required")
        result[key] = Path(path).resolve()
    return result


def _load(case: dict, attempt: Path, result_path: Path, diagnostic: bool,
          review: dict) -> dict:
    case_id = case["case_id"]
    config = read(attempt / "config.json")
    construction = read(attempt / "construction.json")
    result = read(result_path)
    site = read(attempt / "site-source.json")
    participant = read(attempt / "participant-source.json")
    context = read(attempt / "context-source.json")
    provenance = read(attempt / "acquisition-provenance.json")
    measured = result.get("measured_values", {})
    if (config.get("selected_case_id") != case_id or
            construction.get("case_id") != case_id or
            result.get("case_id") != case_id or
            measured.get("case_id") != case_id):
        raise ValueError("comparison case identity differs: " + case_id)
    if (measured.get("frame_count") != 900 or
            measured.get("source_sha256") != {
                "site": sha(attempt / "site-source.json"),
                "participant": sha(attempt / "participant-source.json"),
                "context": sha(attempt / "context-source.json")
            } or measured.get("road_user_kind_from_source") != case["road_user_kind"] or
            measured.get("exception_kind_from_source") != case["exception_request"]):
        raise ValueError("comparison measurement lacks original packet join")
    if (participant.get("road_user_kind") != case["road_user_kind"] or
            context.get("exception_kind") != case["exception_request"] or
            site.get("assignment_id") != case_id.rsplit("__", 1)[0]):
        raise ValueError("comparison source packet differs from selected case")
    if diagnostic:
        if (provenance.get("provenance_kind") != "synthetic_fixture" or
                provenance.get("diagnostic_fixture") is not True or
                result.get("diagnostic_fixture") is not True):
            raise ValueError("comparison diagnostic source is not a CPU fixture")
    else:
        if (provenance.get("provenance_kind") != "native" or
                provenance.get("diagnostic_fixture") is not False):
            raise ValueError("comparison requires original Native source")
        from cycle_lane_source_audit import audit
        independent = audit(attempt, review[case_id], case_id)
        if any(measured.get(key) != value for key, value in
               independent["measurement"].items()):
            raise ValueError("comparison independent Native measurement differs")
    return {"case_id": case_id, "config": config, "site": site,
            "participant": participant, "context": context,
            "measured": measured, "result_sha256": sha(result_path)}


def audit_comparison(comparison_id: str, attempts: dict[str, Path],
                     results: dict[str, Path], diagnostic: bool,
                     review: dict | None = None) -> dict:
    plan = read(ROOT / "case-plan.json")
    comparison = next((c for c in plan["comparisons"]
                       if c["comparison_id"] == comparison_id), None)
    if comparison is None:
        raise ValueError("unknown exact comparison")
    selected = comparison["case_ids"]
    if set(attempts) != set(selected):
        raise ValueError("all and only comparison cases require attempts")
    if set(results) - set(selected):
        raise ValueError("result belongs to another comparison")
    cases = {c["case_id"]: c for c in plan["cases"]}
    loaded = [_load(cases[cid], attempts[cid],
                    results.get(cid, attempts[cid] / "result.json"),
                    diagnostic, review or {}) for cid in selected]
    deliberate = [name for name in TARGETS
                  if len({cases[cid][name] for cid in selected}) > 1]
    if len(deliberate) != 1:
        raise ValueError("comparison must vary exactly one declared target")
    fixed_targets = [name for name in TARGETS if name not in deliberate]
    for name in fixed_targets:
        if len({cases[cid][name] for cid in selected}) != 1:
            raise ValueError("fixed comparison target changed: " + name)
    fixed = {
        "motor_vehicle_actor": lambda row: row["config"].get("actor"),
        "camera_plan": lambda row: row["config"].get("cameras"),
        "duration_s": lambda row: row["config"].get("duration_s"),
        "rate_hz": lambda row: row["config"].get("rate_hz"),
        "site_map": lambda row: row["site"].get("map_id"),
        "facility_id": lambda row: row["site"].get("facility_id"),
        "facility_polygon": lambda row: row["site"].get("facility_polygon"),
        "conflict_polygon": lambda row: row["site"].get("conflict_polygon"),
        "participant_route": lambda row: row["site"].get("routes", {}).get(
            row["case_id"].split("__")[-1], {}).get("participant"),
    }
    if deliberate[0] != "road_user_kind":
        fixed["participant_blueprint"] = lambda row: row["participant"].get("actor_blueprint_id")
    for name, value in fixed.items():
        signatures = {json.dumps(value(row), sort_keys=True) for row in loaded}
        if "null" in signatures:
            raise ValueError("fixed comparison condition missing: " + name)
        if len(signatures) != 1:
            raise ValueError("fixed comparison condition changed: " + name)
    for row in loaded:
        measured = row["measured"]
        if (measured.get("observed_precedence") not in
                {"ego_first", "participant_first", "same_frame_unresolved"} or
                not isinstance(measured.get("ego_facility_frames"), int) or
                not isinstance(measured.get("participant_facility_frames"), int)):
            raise ValueError("comparison original occupancy/precedence missing")
    return {"format": "cycle-lane-2703-comparison-audit-v1",
            "comparison_id": comparison_id, "case_ids": selected,
            "deliberate_target": deliberate[0], "fixed_conditions_checked": list(fixed),
            "observed": {row["case_id"]: {
                "precedence": row["measured"]["observed_precedence"],
                "ego_facility_frames": row["measured"]["ego_facility_frames"],
                "participant_facility_frames": row["measured"]["participant_facility_frames"],
                "result_sha256": row["result_sha256"]} for row in loaded},
            "diagnostic_fixture": diagnostic,
            "physical_acceptance_claimed": False,
            "legal_verdict": None}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--comparison", required=True)
    parser.add_argument("--attempt", action="append", default=[])
    parser.add_argument("--result", action="append", default=[])
    parser.add_argument("--diagnostic", action="store_true")
    parser.add_argument("--review", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if not args.diagnostic and args.review is None:
        raise ValueError("independent original review hashes required")
    result = audit_comparison(args.comparison, _named(args.attempt),
                              _named(args.result), args.diagnostic,
                              read(args.review) if args.review else {})
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
