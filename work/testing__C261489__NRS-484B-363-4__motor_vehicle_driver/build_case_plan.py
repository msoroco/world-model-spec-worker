"""Regenerate the exact school-zone overtaking coverage plan from frozen inputs."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
ASSIGNMENT = "testing__C261489__NRS-484B-363-4__motor_vehicle_driver"
HERE = ROOT / "work" / ASSIGNMENT
INPUT = ROOT / "inputs" / ASSIGNMENT
LAW = "NRS-484B-363-4"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def case(name: str, condition: str, gap_ids: list[str], *, pass_requested: bool = True) -> dict:
    return {
        "case_id": f"{ASSIGNMENT}__{name}",
        "case_kind": "physical_capture_probe",
        "kind": "delivery",
        "condition": condition,
        "gap_ids": gap_ids,
        "capture_frames": 900,
        "fps": 20,
        "pass_requested": pass_requested,
        "construction": "school_pass.py:construct",
        "measurement": "school_pass.py:measure_original",
        "timing_audit": "school_timing.py:derive",
        "physical_risk": "The actual pass and physical beacon indication require a reviewed route and synchronized original camera/device readback.",
        "target_law_id": LAW,
    }


def comparison(name: str, left: str, right: str, difference: str) -> dict:
    return {
        "comparison_id": name,
        "case_ids": [f"{ASSIGNMENT}__{left}", f"{ASSIGNMENT}__{right}"],
        "fixed_conditions": "Same driver and vehicle classes, school-zone extent, lane geometry, route and same-direction target; only stated source-backed condition changes. All cases use 20 Hz, 45 s and four synchronized cameras.",
        "deliberate_differences": difference,
    }


def main() -> None:
    old = json.loads((HERE / "case-plan.json").read_text())
    assignment = json.loads((INPUT / "assignment.json").read_text())
    evidence = json.loads((INPUT / "evidence.json").read_text())
    assert evidence["recordings"] == [], "re-review accepted evidence before regenerating"
    cases = [
        case("active_beacon_pass", "School in session; within operation and outside class hours; operational alternating beacon flashes, same-direction pass inside zone", ["g-overlap", "g-beacon", "g-time"]),
        case("school_not_in_session", "School calendar confirms no session on the local day; same passing motion", ["g-calendar"]),
        case("after_end_29m", "Passing 29 minutes after last school operation end, before the statutory half-hour interval starts", ["g-half-hour"]),
        case("after_end_30m", "Passing exactly 30 minutes after last operation end; preserve boundary uncertainty", ["g-half-hour"]),
        case("after_end_31m", "Passing 31 minutes after last operation end, within the between-operation interval", ["g-half-hour"]),
        case("before_start_31m", "Passing 31 minutes before next operation begins, within the between-operation interval", ["g-half-hour"]),
        case("before_start_30m", "Passing exactly 30 minutes before next operation begins; preserve boundary uncertainty", ["g-half-hour"]),
        case("before_start_29m", "Passing 29 minutes before next operation begins, after the between-operation interval", ["g-half-hour"]),
        case("class_no_flash", "During independently sourced pupil class hours, operational beacon with two yellow lights but no alternating flash indication", ["g-class-flash"]),
        case("sign_without_operational_beacon", "Zone governed by sign without an operational speed-limit beacon; sign indicates limit not in effect", ["g-sign"]),
        case("no_pass", "Same active zone and beacon but ego remains behind target, with no completed overtake and pass", ["g-overlap"], pass_requested=False),
        case("outside_zone", "Same passing route shifted outside surveyed school-zone extent; source records the shifted location", ["g-zone"]),
    ]
    comparisons = [
        comparison("pass_activation", "active_beacon_pass", "no_pass", "Completed same-direction overtake and pass versus no pass"),
        comparison("zone_extent", "active_beacon_pass", "outside_zone", "Measured pass inside versus outside the surveyed designated extent"),
        comparison("school_session", "active_beacon_pass", "school_not_in_session", "School-calendar session day versus no-session day"),
        comparison("after_end_lower_boundary", "after_end_29m", "after_end_30m", "Source-clock pass time 29 versus 30 minutes after operation end"),
        comparison("after_end_upper_probe", "after_end_30m", "after_end_31m", "Source-clock pass time 30 versus 31 minutes after operation end"),
        comparison("before_start_lower_probe", "before_start_31m", "before_start_30m", "Source-clock pass time 31 versus 30 minutes before operation start"),
        comparison("before_start_upper_boundary", "before_start_30m", "before_start_29m", "Source-clock pass time 30 versus 29 minutes before operation start"),
        comparison("class_beacon_indication", "active_beacon_pass", "class_no_flash", "Source-backed pupil class hours and observed beacon indication; all other school-zone facts fixed"),
        comparison("sign_without_operational_beacon", "class_no_flash", "sign_without_operational_beacon", "Operational beacon designation versus sign-only governance; the sign says limit inactive in the latter"),
    ]
    gaps = [
        ("g-overlap", "Original driver and two same-direction vehicle trajectories establishing a completed pass, or an observed no-pass reference"),
        ("g-zone", "Surveyed designated school-zone extent and map/property reference proving pass location"),
        ("g-beacon", "Original sign plus two or more yellow lamps, alternating capability and actual indication over the passing interval"),
        ("g-time", "Independent local civil clock, school calendar, operation schedule and pupil class hours"),
        ("g-calendar", "School-day session status from original calendar source"),
        ("g-half-hour", "Original local-clock pass time and operation schedule around both exact thirty-minute statutory boundaries"),
        ("g-class-flash", "Independent class-hour source and actual nonflashing beacon-state readback"),
        ("g-sign", "Source-backed sign-only zone designation and contemporaneous inactive-limit instruction"),
    ]
    old["cases"] = cases
    old["comparisons"] = comparisons
    old["observations"] = [
        {"name": name, "mandatory": True, "reason": reason}
        for name, reason in [
            ("same_direction_pass", "Original ego and target IDs, class, body footprints, route progress and longitudinal order per frame"),
            ("designated_zone_extent", "Source-hashed surveyed map, designation and zone boundary joined to pass frames"),
            ("beacon_sign_readback", "Sign identity, two or more yellow lamps, alternating pattern and synchronized device state"),
            ("school_schedule_and_clock", "Independent local clock, calendar, operation end/start and pupil class interval sources"),
            ("four_camera_pixels", "900 original time-joined frames for each canonical camera and composition"),
        ]
    ]
    old["camera_plan"] = {
        "profile": "overview1080-capability", "duration_s": 45,
        "composition": "synchronized_four_view_primary",
        "coverage": [
            {"view": view, "subject": "ego and target pass, designated zone, beacon/sign and reference clock", "interval": "full 45 s"}
            for view in ("overview", "approach", "reference_corner", "driver_reference")
        ],
    }
    old["source_observation_mapping"] = {}
    old["evidence_review"] = {
        "reviewer": "CPU worker", "method": "Read every frozen evidence inventory entry; this assignment has no accepted recordings. The package therefore requests original source-bound captures without claiming prior coverage.",
        "facts": [],
        "gaps": [
            {"id": key, "requirement": requirement, "source": assignment["law"]["source"],
             "why_existing_insufficient": "The frozen evidence inventory contains no accepted recording for this assignment."}
            for key, requirement in gaps
        ],
    }
    old["requirement_dispositions"] = [
        {"disposition_index": index, "requirement": req, "source": assignment["law"]["source"],
         "status": "selected_required", "case_ids": [item["case_id"] for item in cases],
         "evidence_or_gap": "No accepted recording in frozen evidence inventory; source-bound new capture planned."}
        for index, req in enumerate((
            "Same-direction overtake and pass in a designated school zone or school crossing zone",
            "No-school-session exception and independent school calendar",
            "Between-operation exception with thirty-minute boundaries on both ends",
            "Operational-beacon class-hours no-flash exception with two or more alternating yellow lights and sign",
            "Sign indication exception when the zone is not designated by an operational speed limit beacon",
        ))
    ]
    old["planning_status"] = "exact_cases_selected_cpu_construction_in_progress"
    old["runtime_uncertainties"] = [
        "Actual CARLA passing motion, map zone designation, lamp pixels and camera coverage remain for original capture and review.",
        "No legal conclusion is drawn from clock arithmetic or synthetic fixture targets.",
    ]
    (HERE / "case-plan.json").write_text(json.dumps(old, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({"cases": len(cases), "comparisons": len(comparisons), "plan_sha256": digest(HERE / "case-plan.json")}))


if __name__ == "__main__":
    main()
