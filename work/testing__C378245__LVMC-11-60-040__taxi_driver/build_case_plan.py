"""Expand the exact taxi-stand prohibition and passenger-exchange exception."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
IDENTITY = "testing__C378245__LVMC-11-60-040__taxi_driver"
CASES = (
    ("designated_stand_park", "in_stand", "park", "none", "designated stand baseline"),
    ("outside_stand_park", "outside_stand", "park", "none", "outside designated stand parking"),
    ("outside_stand_stand", "outside_stand", "stand", "none", "outside designated stand standing"),
    ("outside_stand_load", "outside_stand", "temporary_stop", "loading", "actual expeditious passenger loading"),
    ("outside_stand_unload", "outside_stand", "temporary_stop", "unloading", "actual expeditious passenger unloading"),
    ("outside_stand_idle_stop", "outside_stand", "temporary_stop", "none", "temporary stop without passenger exchange"),
)


def build() -> dict:
    path = ROOT / "case-plan.json"
    plan = json.loads(path.read_text())
    if plan["assignment_id"] != IDENTITY or plan["cell_id"] != "C378245":
        raise ValueError("frozen package identity differs")
    ids = {suffix: IDENTITY + "__" + suffix for suffix, *_ in CASES}
    camera = {
        "duration_s": 45, "rate_hz": 20,
        "views": ["overview", "approach", "curb_reference", "passenger_side"],
        "profile": "overview1080-capability",
        "composition": "synchronized_four_view_primary",
    }
    channels = [
        {"name": "reviewed_stand_and_street", "source": "original designation, authority, marking, curb and jurisdiction survey"},
        {"name": "taxicab_and_operator", "source": "original licensing, fee-service and operator review"},
        {"name": "taxi_body_and_halt", "source": "900 original 20 Hz Native body/velocity/road-lane samples"},
        {"name": "passenger_exchange", "source": "original door/person/boarding events joined to four camera pixels and independent review"},
        {"name": "other_regulations", "source": "identified applicable original stop/parking rules and review; no automatic legal verdict"},
    ]
    plan["camera_plan"] = camera
    plan["observations"] = [{"name": row["name"], "source": row["source"], "mandatory": True}
                            for row in channels]
    plan["source_observation_mapping"] = {}
    plan["cases"] = [
        {
            "case_id": ids[suffix], "kind": "planned_controlled_construction",
            "target_law_id": "LVMC-11-60-040", "branch_ids": ["taxi_stand_parking", "passenger_loading_exception"],
            "target": purpose, "gap_ids": ["no_accepted_original_source"],
            "location_request": location, "halt_activity_request": activity,
            "passenger_exchange_request": exchange,
            "physical_risk": "Actual stand boundary, curb footprint, taxi halt and passenger exchange need source review and original CARLA realization.",
            "recording_description": {"duration_s": 45, "rate_hz": 20,
                "cameras": camera["views"], "channels": channels,
                "uncertainty": "Engineering request only; expeditiousness and other-regulation compliance remain for independent review."},
        }
        for suffix, location, activity, exchange, purpose in CASES
    ]
    def comparison(name, suffixes, fixed, difference):
        return {"comparison_id": name, "case_ids": [ids[x] for x in suffixes],
                "fixed_conditions": fixed, "deliberate_differences": difference}
    common = ["same C378245 business-district street and taxi/driver identity",
              "same reviewed stand designation and curb map", "same four-camera 20 Hz 45 s plan"]
    plan["comparisons"] = [
        comparison("designated_versus_outside_park", ("designated_stand_park", "outside_stand_park"),
                   common + ["same parking action and passenger inactivity"], ["taxi body inside versus outside designated stand polygon"]),
        comparison("outside_park_versus_stand", ("outside_stand_park", "outside_stand_stand"),
                   common + ["same outside-stand location and no passenger exchange"], ["observed park versus stand activity"]),
        comparison("passenger_exchange_exception", ("outside_stand_load", "outside_stand_unload", "outside_stand_idle_stop"),
                   common + ["same outside-stand halt location and other-regulation source"],
                   ["actual passenger loading versus unloading versus no exchange"]),
        comparison("parking_versus_loading", ("outside_stand_park", "outside_stand_load"),
                   common + ["same outside-stand taxi location and other-regulation source"],
                   ["park without passenger exchange versus temporary active loading"]),
    ]
    plan["requirement_dispositions"] = [
        {"status": "selected_required", "disposition_index": index, "source": "LVMC 11.60.040 exact law text",
         "requirement": requirement, "case_ids": members,
         "evidence_or_gap": "No accepted original recording; selected source-gated comparison needs reviewed stand, street, taxi, activity and passenger evidence."}
        for index, (requirement, members) in enumerate((
            ("Taxicab operator, street and officially designated taxicab stand", list(ids.values())),
            ("No standing or parking on street outside the designated stand",
             [ids[x] for x in ("designated_stand_park", "outside_stand_park", "outside_stand_stand")]),
            ("Temporary stop for and while actually expeditiously loading or unloading passengers, in accordance with other regulations",
             [ids[x] for x in ("outside_stand_load", "outside_stand_unload", "outside_stand_idle_stop")]),
        ))
    ]
    plan["evidence_review"]["gaps"] = [{
        "id": "no_accepted_original_source",
        "requirement": "Original taxi stand designation, street/curb, taxi licence, operator, activity, passenger and other-rule evidence",
        "why_existing_insufficient": "Frozen evidence inventory contains zero accepted recordings; no physical fact or source-backed reuse is established.",
        "source": plan["sources"][0],
    }]
    plan["planning_status"] = "selected_source_gated_cpu_construction_in_progress"
    return plan


if __name__ == "__main__":
    plan = build()
    (ROOT / "case-plan.json").write_text(json.dumps(plan, indent=2, sort_keys=True) + "\n")
    print(len(plan["cases"]), len(plan["comparisons"]))
