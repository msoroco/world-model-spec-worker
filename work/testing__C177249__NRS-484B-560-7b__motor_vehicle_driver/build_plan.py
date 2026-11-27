"""Write the exact railway-device and officer comparison plan."""
from __future__ import annotations

import json
from pathlib import Path

import railway_7b as law

HERE = Path(__file__).resolve().parent
AID = HERE.name


def build():
    path = HERE / "case-plan.json"
    plan = json.loads(path.read_text())
    ids = {name: AID + "__" + name for name in law.CASES}
    rationale = {
        "device_stop_halt": "Specific source-reviewed crossing device displays a stop instruction; the driver halts before the crossing entry.",
        "device_stop_cross": "The same crossing device displays a stop instruction; the driver enters the crossing during that indication.",
        "device_clear_cross": "The same device displays a permissive clear indication; the driver enters and clears the crossing.",
        "device_clear_halt": "The same device displays a permissive clear indication; the driver independently halts. Clear is not construed as an affirmative command to proceed.",
        "officer_stop_halt": "An actual sourced police officer directs this driver to stop while the installed device remains present; the driver halts.",
        "officer_stop_cross": "The same officer directs the driver to stop while the installed device remains present; the driver enters the crossing.",
    }
    plan["topic_inventory"] = {
        "exact-text": plan["law_text"],
        "device": "obey an official traffic-control device at a railroad crossing",
        "officer": "obey the directions of a police officer at a railroad crossing",
    }
    plan["cases"] = [
        {"case_id": ids[name], "target_law_id": law.LAW, "target_type": "delivery",
         "rationale": rationale[name], "gap_ids": ["gap-device" if axis == "device" else "gap-officer"],
         "source_packet_required": True}
        for name, (axis, _, _) in law.CASES.items()
    ]
    pairs = [
        ("device_stop_response", "device_stop_halt", "device_stop_cross",
         "actual body halt versus crossing entry while stop instruction remains active"),
        ("device_indication", "device_stop_cross", "device_clear_cross",
         "actual source-observed stop versus permissive clear indication"),
        ("clear_response", "device_clear_cross", "device_clear_halt",
         "actual crossing entry versus independent halt under permissive indication"),
        ("officer_stop_response", "officer_stop_halt", "officer_stop_cross",
         "actual body halt versus crossing entry during the same officer stop direction"),
        ("governing_channel", "device_stop_halt", "officer_stop_halt",
         "source-reviewed device versus actual officer stop channel"),
    ]
    plan["comparisons"] = [
        {"comparison_id": key, "case_ids": [ids[left], ids[right]],
         "fixed_conditions": ["C177249 paved road and rail crossing geometry", "ordinary motor vehicle and driver",
                              "road approach and governed movement", "crossing boundaries and route",
                              "45 s at 20 Hz", "four synchronized camera views"],
         "deliberate_differences": [difference]}
        for key, left, right, difference in pairs
    ]
    names = ["rail_crossing_geometry", "device_identity_and_officiality", "device_indication_history",
             "governed_movement", "officer_identity_and_direction_history", "driver_identity",
             "original_body_entry_exit", "actual_speed_and_brake", "four_camera_frame_join"]
    plan["observations"] = [
        {"name": name, "mandatory": True,
         "source": "reviewed original site packet and frame-joined Native capture; officer source required for officer cases"}
        for name in names
    ]
    plan["source_observation_mapping"] = {}
    plan["evidence_review"]["method"] = "Reviewed the frozen evidence inventory (zero accepted recordings), exact law text and conditional witness. No prior recording establishes either instruction channel or physical response."
    plan["evidence_review"]["gaps"] = [
        {"id": "gap-device", "requirement": "official device provenance, actual crossing instruction and actual driver response",
         "source": "NRS 484B.560(7)(b); conditional frozen witness index 462",
         "why_existing_insufficient": "Frozen evidence inventory has zero accepted recordings."},
        {"id": "gap-officer", "requirement": "actual police officer direction at the railroad crossing and driver response",
         "source": "NRS 484B.560(7)(b)",
         "why_existing_insufficient": "Frozen evidence inventory has zero accepted recordings."},
    ]
    plan["requirement_dispositions"] = [
        {"disposition_index": 0, "requirement": "obey an official traffic-control device at a railroad crossing",
         "source": "NRS 484B.560(7)(b)", "status": "selected_required",
         "evidence_or_gap": "gap-device", "case_ids": [ids[x] for x in law.CASES if x.startswith("device_")]},
        {"disposition_index": 1, "requirement": "obey the directions of a police officer at a railroad crossing",
         "source": "NRS 484B.560(7)(b)", "status": "selected_required",
         "evidence_or_gap": "gap-officer", "case_ids": [ids[x] for x in law.CASES if x.startswith("officer_")]},
    ]
    plan["camera_plan"] = {
        "profile": "overview1080-capability", "duration_s": 45,
        "composition": "synchronized_four_view_primary",
        "coverage": [
            {"view": "overview", "subject": "crossing, device or officer, and complete vehicle", "interval": "entire 45 s"},
            {"view": "approach", "subject": "device indication, officer direction and vehicle approach", "interval": "entire 45 s"},
            {"view": "reference_corner", "subject": "rail crossing entry and exit boundaries", "interval": "entire 45 s"},
            {"view": "driver_reference", "subject": "driver-view device or officer communication", "interval": "entire 45 s"},
        ],
    }
    plan["judgment_range_inventory"] = []
    plan["planning_status"] = "construction_in_progress"
    plan["runtime_uncertainties"] = [
        "Official placement, governing instruction and actual officer identity require independent original source review.",
        "Actual CARLA body motion, realized device indication, officer direction and four-view pixels remain physical checks.",
        "A permissive clear indication is not treated as a legal duty to proceed; no legal verdict is generated.",
    ]
    path.write_text(json.dumps(plan, sort_keys=True, indent=2) + "\n")
    return len(ids)


if __name__ == "__main__":
    print(build())
