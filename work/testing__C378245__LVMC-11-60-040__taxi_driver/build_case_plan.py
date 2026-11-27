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
        "views": ["overview", "approach", "reference_corner", "driver_reference"],
        "profile": "overview1080-capability",
        "composition": "synchronized_four_view_primary",
        "coverage": [
            {"view": "overview", "subject": "taxi, stand, street and passenger",
             "interval": "full capture"},
            {"view": "approach", "subject": "taxi approach and curb position",
             "interval": "full capture"},
            {"view": "reference_corner", "subject": "stand designation boundary",
             "interval": "full capture"},
            {"view": "driver_reference", "subject": "passenger side and taxi door",
             "interval": "full capture"},
        ],
    }
    channels = [
        {"name": "native_frame", "unit": "frame", "sampling_rate_hz": 20,
         "method": "original CARLA world tick readback", "time_window": "full 900-frame, 45-second capture",
         "reference_frame": "original CARLA world", "uncertainty": "one retained 20 Hz sample"},
        {"name": "taxi_center_xy_m", "unit": "m", "sampling_rate_hz": 20,
         "method": "original taxi transform readback", "time_window": "full 900-frame, 45-second capture",
         "reference_frame": "reviewed Native map XY", "uncertainty": "Native transform precision"},
        {"name": "taxi_footprint_xy_m", "unit": "m", "sampling_rate_hz": 20,
         "method": "original taxi bounding box transformed into reviewed Native map XY",
         "time_window": "full 900-frame, 45-second capture",
         "reference_frame": "reviewed Native map XY", "uncertainty": "Native bounding box geometry"},
        {"name": "taxi_speed_mps", "unit": "m/s", "sampling_rate_hz": 20,
         "method": "original taxi velocity readback", "time_window": "full 900-frame, 45-second capture",
         "reference_frame": "original CARLA world", "uncertainty": "0.1 m/s engineering halt tolerance is not a legal cutoff"},
        {"name": "four_camera_frames", "unit": "native pixels", "sampling_rate_hz": 20,
         "method": "four synchronized original RGB camera sources and SHA-256 frame ledger",
         "time_window": "full 900-frame, 45-second capture",
         "reference_frame": "original CARLA world and frame identity", "uncertainty": "camera visibility requires independent review"},
        {"name": "passenger_activity_review", "unit": "source record", "sampling_rate_hz": 20,
         "method": "independent reviewed actor/door/boarding or alighting record bound to original cameras",
         "time_window": "reviewed halt interval within full capture",
         "reference_frame": "original Native frame identity", "uncertainty": "activity and expeditiousness require human review"},
    ]
    context_inputs = [
        {"name": name, "unit": "source record", "method": "SHA-bound original independent review"}
        for name in ("taxi_stand_designation", "business_district_and_street",
                     "taxi_licence_and_operator", "other_stopping_parking_regulations")
    ]
    plan["camera_plan"] = camera
    plan["observations"] = [{"name": row["name"], "source": row["method"], "mandatory": True}
                            for row in channels]
    plan["acquisition_source_mapping"] = {
        "native_frame": {"evidence": "Native tick ledger", "channels": ["native_frame"], "source_refs": ["native_frames.json"]},
        "taxi_center_xy_m": {"evidence": "taxi transform", "channels": ["taxi_center_xy_m"], "source_refs": ["native_frames.json"]},
        "taxi_footprint_xy_m": {"evidence": "taxi body corners", "channels": ["taxi_footprint_xy_m"], "source_refs": ["native_frames.json"]},
        "taxi_speed_mps": {"evidence": "taxi velocity", "channels": ["taxi_speed_mps"], "source_refs": ["native_frames.json"]},
        "four_camera_frames": {"evidence": "original four-view frame ledger and pixels", "channels": ["four_camera_frames"], "source_refs": ["native_frames.json"]},
        "passenger_activity_review": {"evidence": "source-hashed independent activity review", "channels": ["passenger_activity_review"], "source_refs": ["activity_review.json"]},
        "taxi_stand_designation": {"evidence": "source-hashed official designation", "channels": [], "source_refs": ["stand_designation.json"]},
        "business_district_and_street": {"evidence": "source-hashed site and jurisdiction", "channels": [], "source_refs": ["reviewed_site.json"]},
        "taxi_licence_and_operator": {"evidence": "source-hashed taxi licence", "channels": [], "source_refs": ["taxi_licence.json"]},
        "other_stopping_parking_regulations": {"evidence": "source-hashed applicable rules", "channels": [], "source_refs": ["other_regulations.json"]},
    }
    # The frozen assignment exports no source_observation_terms. Preserve the
    # useful acquisition inventory above while matching that exact term set.
    plan["source_observation_mapping"] = {}
    plan["cases"] = [
        {
            "case_id": ids[suffix], "kind": "planned_controlled_construction",
            "target_law_id": "LVMC-11-60-040", "branch_ids": ["taxi_stand_parking", "passenger_loading_exception"],
            "target": purpose, "gap_ids": ["no_accepted_original_source"],
            "location_request": location, "halt_activity_request": activity,
            "passenger_exchange_request": exchange,
            "physical_risk": "Actual stand boundary, curb footprint, taxi halt and passenger exchange need source review and original CARLA realization.",
            "recording_description": {"channels": channels, "context_inputs": context_inputs,
                "limitations": ["Requested activity is not observed legal activity.",
                                "Expeditiousness and other-regulation compliance remain for independent review.",
                                "No accepted original taxi recording is supplied in frozen evidence."]},
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
