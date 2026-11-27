"""Build the source-bound nighttime parking comparison plan."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ASSIGNMENT = json.loads((ROOT / "case-plan.json").read_text())["assignment_id"]


def case(suffix, duration_s, start_local, vehicle_class="nonmotor", purpose="parking"):
    return {
        "case_id": f"{ASSIGNMENT}__{suffix}",
        "target_law_id": "LVMC-11-52-300",
        "gap_ids": ["no_accepted_original_parking_episode"],
        "design": {
            "start_local": start_local,
            "duration_s": duration_s,
            "vehicle_class": vehicle_class,
            "purpose": purpose,
            "other_vehicle": "present; original body and state required",
            "street": "same qualifying street and Las Vegas jurisdiction",
        },
        "measurement_rule": "Measure original continuously parked interval and its overlap with local civil 01:00–06:00; classification and parking purpose require independent source records.",
    }


def comparison(name, left, right, differences):
    return {
        "comparison_id": name,
        "case_ids": [f"{ASSIGNMENT}__{left}", f"{ASSIGNMENT}__{right}"],
        "fixed_conditions": ["qualifying street and jurisdiction", "same physical carriage and other vehicle geometry", "20 Hz four-view capture", "parking start and end source method unless changed below"],
        "deliberate_differences": differences,
    }


def main():
    plan = json.loads((ROOT / "case-plan.json").read_text())
    plan["cases"] = [
        case("night_29m59s", 1799, "02:00:00"),
        case("night_30m00s", 1800, "02:00:00"),
        case("night_30m01s", 1801, "02:00:00"),
        case("outside_window_30m01s", 1801, "00:10:00"),
        case("motor_vehicle_30m01s", 1801, "02:00:00", vehicle_class="motor"),
        case("loading_30m01s", 1801, "02:00:00", purpose="actual_loading"),
        case("boundary_01m", 1801, "00:59:59"),
        case("boundary_06m", 1801, "05:59:59"),
    ]
    plan["comparisons"] = [
        comparison("duration_below_at", "night_29m59s", "night_30m00s", ["measured parked duration 1799 versus 1800 seconds"]),
        comparison("duration_at_above", "night_30m00s", "night_30m01s", ["measured parked duration 1800 versus 1801 seconds"]),
        comparison("night_vs_day", "night_30m01s", "outside_window_30m01s", ["civil clock interval"]),
        comparison("nonmotor_exception", "night_30m01s", "motor_vehicle_30m01s", ["source-proven vehicle classification and motive power"]),
        comparison("parking_vs_loading", "night_30m01s", "loading_30m01s", ["actual loading activity and parking purpose"]),
        comparison("one_am_boundary", "night_30m01s", "boundary_01m", ["civil clock entry across 01:00"]),
        comparison("six_am_boundary", "night_30m01s", "boundary_06m", ["civil clock exit across 06:00"]),
    ]
    plan["observations"] = [
        {"name": "original_body_state", "mandatory": True, "source": "Native per-frame body, velocity, street intersection"},
        {"name": "civil_time", "mandatory": True, "source": "original timestamp plus independently recorded IANA time zone and date"},
        {"name": "vehicle_classification", "mandatory": True, "source": "physical build/source dossier; motive power and exclusions, independent of actor label"},
        {"name": "parking_activity", "mandatory": True, "source": "actual loading/unloading, person responsibility, stationary episode boundaries"},
        {"name": "street_jurisdiction", "mandatory": True, "source": "source map and municipality/public access dossier"},
        {"name": "other_vehicle_body_state", "mandatory": True, "source": "second original Native actor body and lifecycle"},
    ]
    plan["requirement_dispositions"] = [{
        "requirement": "LVMC-11-52-300",
        "source": "LVMC 11.52.300 exact frozen text",
        "status": "selected_required",
        "evidence_or_gap": "No accepted recording; eight source-bound proposed episodes cover duration, time window, nonmotor scope, and parking activity. Physical classification remains unverified.",
        "case_ids": [x["case_id"] for x in plan["cases"]],
        "disposition_index": 0,
    }]
    plan["evidence_review"]["gaps"] = [{
        "id": "no_accepted_original_parking_episode",
        "requirement": "LVMC-11-52-300",
        "source": "inputs/" + ASSIGNMENT + "/evidence.json",
        "why_existing_insufficient": "The frozen accepted-recording inventory is empty; no original parking duration, time, vehicle classification, or street source is available.",
    }]
    plan["source_observation_mapping"] = {}
    plan["planning_status"] = "source_bound_exact_cases_pending_construction"
    plan["runtime_uncertainties"] = [
        "Carriage qualification, jurisdiction, parking rather than actual temporary loading, and vehicle definition exclusions require external source dossiers and independent review.",
        "Actual 1801-second continuous capture at 20 Hz with four views is a physical cost and retention risk; no original recording exists yet.",
        "Meaning of statutory endpoints at exactly 01:00 and 06:00 and cross-window counting remains a legal review question; engineering measurements do not decide it.",
    ]
    (ROOT / "case-plan.json").write_text(json.dumps(plan, indent=2) + "\n")


if __name__ == "__main__":
    main()
