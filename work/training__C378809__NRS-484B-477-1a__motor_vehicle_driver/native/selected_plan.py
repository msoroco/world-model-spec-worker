"""Source-gated C378809 alley parking requests and comparison invariants.

These requests are engineering intents. A source review must establish the
alley, business district, ordinance and actual goods activity independently.
"""
import json
from pathlib import Path


ASSIGNMENT = "training__C378809__NRS-484B-477-1a__motor_vehicle_driver"
CELL = {"layout": "business_district_alley", "maneuver": "park",
        "control": "alley_entrance"}
CASES = {
    ASSIGNMENT + "__probe_01": {"goods_motion_requested": True,
                                 "idle_after_goods_requested": False,
                                 "goods_motion_frame": 480},
    ASSIGNMENT + "__probe_02": {"goods_motion_requested": False,
                                 "idle_after_goods_requested": False,
                                 "goods_motion_frame": None},
    ASSIGNMENT + "__probe_03": {"goods_motion_requested": True,
                                 "idle_after_goods_requested": True,
                                 "goods_motion_frame": 200},
}
SOURCE_KEYS = (
    "map_name", "alley_boundary_source_id", "entrance_source_id",
    "highway_public_use_source_id", "city_block_source_id",
    "rear_property_service_source_id", "not_cul_de_sac_source_id",
    "frontage_600ft_source_id", "frontage_300ft_source_id",
    "building_uses_source_id", "local_authority_source_id",
    "ordinance_status_source_id", "goods_prop_source_id",
    "goods_origin_source_id", "goods_destination_source_id",
)


def require(ok, message):
    if not ok:
        raise ValueError(message)


def review_survey(source):
    """Reject an unreviewed site; source IDs are locators, not legal verdicts."""
    require(source.get("source_kind") == "original_native_alley_survey",
            "original alley survey required")
    require(source.get("fixed_cell") == CELL, "survey cell mismatch")
    for key in SOURCE_KEYS:
        require(isinstance(source.get(key), str) and source[key].strip(),
                "missing original source: " + key)
    require(source.get("ordinance_status") in
            ("none_applicable", "applicable_otherwise", "unknown"),
            "source-reviewed ordinance status required")
    require(len(source.get("spawn_xyz_yaw_deg", [])) == 4 and
            len(source.get("park_xyz_m", [])) == 3 and
            len(source.get("goods_origin_xyz_m", [])) == 3 and
            len(source.get("goods_destination_xyz_m", [])) == 3 and
            source.get("vehicle_blueprint") and source.get("goods_blueprint"),
            "source-aligned vehicle and goods geometry required")
    require(source.get("reviewer") and source.get("reviewed_source_sha256"),
            "independent site review required")
    return source


def plan(case_id, survey):
    require(case_id in CASES, "unknown exact case")
    review_survey(survey)
    request = CASES[case_id]
    return {"case_id": case_id, "fixed_cell": CELL,
            "site_source_sha256": survey["reviewed_source_sha256"],
            "goods_motion_requested": request["goods_motion_requested"],
            "idle_after_goods_requested": request["idle_after_goods_requested"],
            "goods_motion_frame": request["goods_motion_frame"],
            "fixed_park_xyz_m": survey["park_xyz_m"],
            "fixed_ordinance_status_source_id": survey["ordinance_status_source_id"],
            "original_goods_observed": None, "expeditiousness": None,
            "legal_result": None, "physical_completion": False}


def compare(plans):
    require(set(plans) == set(CASES), "three exact comparison members required")
    for case_id, request in CASES.items():
        require(plans[case_id]["goods_motion_requested"] == request["goods_motion_requested"]
                and plans[case_id]["idle_after_goods_requested"] == request["idle_after_goods_requested"]
                and plans[case_id]["goods_motion_frame"] == request["goods_motion_frame"],
                "case request changed")
    fixed = ("fixed_cell", "site_source_sha256", "fixed_park_xyz_m",
             "fixed_ordinance_status_source_id")
    for field in fixed:
        require(all(plans[c][field] == plans[next(iter(CASES))][field]
                    for c in CASES), "comparison fixed source changed: " + field)
    return {"case_ids": list(CASES), "fixed_source_fields": list(fixed),
            "deliberate_differences": ["requested goods motion",
                                       "requested post-goods idle duration via motion frame"],
            "actual_goods_transfer_observed": None,
            "expeditiousness": None, "legal_result": None}


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--survey", required=True)
    args = parser.parse_args()
    survey = json.loads(Path(args.survey).read_text())
    print(json.dumps(compare({case: plan(case, survey) for case in CASES}),
                     sort_keys=True))
