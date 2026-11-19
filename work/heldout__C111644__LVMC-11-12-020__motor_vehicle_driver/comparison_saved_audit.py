"""Recompute exact turn comparisons from saved synthetic original sources.

Planned sweep targets are kept separate from measured body motion. This CPU
audit makes no claim of lawful obedience, Native motion, or actual pixels.
"""

from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from physical_fixture import REQUIRED
from turn_marking import analyze_original_sources


HERE = Path(__file__).resolve().parent


def read(path):
    return json.loads(Path(path).read_text())


def rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines()
            if line.strip()]


def require(condition, reason):
    if not condition:
        raise ValueError(reason)


def source_case(entry, audit):
    path = Path(audit["attempt"]).resolve()
    measured = analyze_original_sources(path)
    require(measured["case_id"] == entry["case_id"], "Comparison case differs")
    require(measured["source_sha256"] == audit["audit"]["original_source_hashes"],
            "Comparison source packet differs from ten-case audit")
    require(audit["construction_sha256"] == entry["construction_sha256"],
            "Comparison construction differs")
    indication = read(path / "turn_indication_original.json")
    plan = read(path / "turn_route_plan.json")
    body = rows(path / "turn_body_original.jsonl")
    require(len(body) == len(measured["samples"]) and len(body) >= 3,
            "Comparison body sample coverage differs")
    # A deleted original must be rejected by the same source verifier.
    with TemporaryDirectory(prefix="turn-comparison-negative-") as temp:
        temp_path = Path(temp)
        for name in REQUIRED:
            if name != "turn_body_original.jsonl":
                (temp_path / name).symlink_to(path / name)
        try:
            analyze_original_sources(temp_path)
        except ValueError as error:
            require("Missing required source: turn_body_original.jsonl" in str(error),
                    "Comparison negative rejected for another reason")
        else:
            raise ValueError("Comparison accepted deleted original body")
    points = plan["target_route_xy_m"]
    course = plan["course_xy_m"]
    planned_offset = ((points[-1][0] - course[-1][0]) ** 2
                      + (points[-1][1] - course[-1][1]) ** 2) ** .5
    return {"case_id": entry["case_id"], "source_hashes": measured["source_sha256"],
            "indication_form": indication["indication_form"],
            "indicated_course_xy_m": indication["indicated_course_xy_m"],
            "intersection_id": indication["intersection_id"],
            "route_variant": plan["route_variant"],
            "planned_route_offset_m": planned_offset,
            "measured_placement_offset_m": measured["placement_offset_m"],
            "maximum_measured_course_deviation_m": max(
                sample["deviation_m"] for sample in measured["samples"]),
            "initial_body_center_xy_m": body[0]["subject"]["center_xy_m"],
            "original_body_sha256": sha256((path / "turn_body_original.jsonl").read_bytes()).hexdigest(),
            "source_frame_count": len(body), "missing_body_rejected": True}


def audit():
    manifest = read(HERE / "execution-manifest.json")
    plan = read(HERE / "case-plan.json")
    source = read(HERE / "all-ten-current-source-audits.json")
    entries = {item["case_id"]: item for item in manifest["cases"]}
    source_rows = {item["case_id"]: item for item in source["cases"]}
    require(set(entries) == set(source_rows) and len(entries) == 10,
            "Ten selected source packets required")
    cases = {case: source_case(entry, source_rows[case])
             for case, entry in entries.items()}
    results = []
    for comparison in plan["comparisons"]:
        ident = comparison["comparison_id"]
        members = [cases[case] for case in comparison["case_ids"]]
        require(len(members) == len(set(comparison["case_ids"])),
                "Duplicate comparison member")
        require(len({x["intersection_id"] for x in members}) == 1
                and len({json.dumps(x["indicated_course_xy_m"]) for x in members}) == 1
                and len({tuple(x["initial_body_center_xy_m"]) for x in members}) == 1
                and len({x["source_frame_count"] for x in members}) == 1,
                "Comparison fixed original context differs: " + ident)
        if ident.endswith("route_response"):
            require(len(members) == 2
                    and len({x["indication_form"] for x in members}) == 1
                    and {x["route_variant"] for x in members} == {"follow", "depart"},
                    "Response pair changed form or route membership")
            follow = next(x for x in members if x["route_variant"] == "follow")
            depart = next(x for x in members if x["route_variant"] == "depart")
            require(depart["maximum_measured_course_deviation_m"]
                    > follow["maximum_measured_course_deviation_m"] + 1,
                    "Response pair lacks measured source separation")
            result = {"measured_deviation_m": [
                follow["maximum_measured_course_deviation_m"],
                depart["maximum_measured_course_deviation_m"]]}
        elif ident == "indication_form":
            require(len(members) == 3
                    and {x["indication_form"] for x in members}
                    == {"marker", "button", "other_indication"}
                    and len({x["original_body_sha256"] for x in members}) == 1
                    and len({x["route_variant"] for x in members}) == 1,
                    "Indication-form control changed motion or form membership")
            result = {"forms": [x["indication_form"] for x in members]}
        elif ident.startswith("course_deviation_"):
            planned = [x["planned_route_offset_m"] for x in members]
            require(sorted(planned) == ([2.0, 4.0] if len(members) == 2
                                        else [2.0, 4.0, 6.0])
                    and len({x["indication_form"] for x in members}) == 1
                    and len({x["original_body_sha256"] for x in members}) == 1,
                    "Course sweep planned offsets or fixed source differ")
            result = {"planned_target_offsets_m": planned,
                      "original_body_sources_equal": True,
                      "actual_motion_separation_verified": False}
        elif ident.startswith("marker_placement_"):
            offsets = [x["measured_placement_offset_m"] for x in members]
            require(sorted(offsets) == ([0.0, .75] if len(members) == 2
                                        else [0.0, .75, 1.5])
                    and len({x["indication_form"] for x in members}) == 1
                    and len({x["original_body_sha256"] for x in members}) == 1,
                    "Placement sweep source offsets or fixed motion differ")
            result = {"source_measured_offsets_m": offsets}
        else:
            raise ValueError("Unknown selected comparison: " + ident)
        results.append({"comparison_id": ident, "case_ids": comparison["case_ids"],
                        "fixed_conditions": comparison["fixed_conditions"],
                        "deliberate_differences": comparison["deliberate_differences"],
                        "missing_original_body_rejected": all(x["missing_body_rejected"]
                                                             for x in members),
                        "result": result, "passed": True})
    require(len(results) == 8, "All eight selected comparisons required")
    return {"format": "worker-current-saved-turn-comparison-audit",
            "assignment_id": HERE.name, "passed": True,
            "source_audits_sha256": sha256((HERE / "all-ten-current-source-audits.json").read_bytes()).hexdigest(),
            "comparisons": results, "native_motion_claimed": False,
            "physical_acceptance_claimed": False, "legal_acceptance_claimed": False}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = audit()
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print("eight_source_bound_saved_comparisons_passed")
