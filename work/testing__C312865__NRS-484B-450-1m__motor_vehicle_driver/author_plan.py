"""Author exact tunnel branch and source-review gaps without legal labels."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
AID = ROOT.name
KINDS = (
    ("outside_stop", "stop", "outside_before_portal", None),
    ("inside_stop", "stop", "inside_tunnel", None),
    ("inside_stand", "stand", "inside_tunnel", None),
    ("inside_park", "park", "inside_tunnel", None),
    ("inside_conflict", "stop", "inside_tunnel", "necessary_avoid_traffic_conflict"),
    ("inside_law", "stop", "inside_tunnel", "compliance_with_law"),
    ("inside_police", "stop", "inside_tunnel", "police_direction"),
    ("inside_device", "stop", "inside_tunnel", "official_device_direction"),
)


def main() -> None:
    path = ROOT / "case-plan.json"
    plan = json.loads(path.read_text())
    evidence_path = Path("inputs") / AID / "evidence.json"
    evidence = json.loads(evidence_path.read_text())
    if evidence.get("recordings") != []:
        raise ValueError("frozen evidence inventory changed; review recordings first")
    gap = {"id": "no-accepted-tunnel-evidence",
           "requirement": "Original highway tunnel boundary, vehicle activity and all stated exception circumstances",
           "source": next(item for item in plan["sources"] if item["path"] == str(evidence_path)),
           "why_existing_insufficient": "Frozen evidence inventory has no accepted original recording."}
    plan["evidence_review"] = {
        "reviewer": "CPU assignment owner",
        "method": "Read exact NRS 484B.450(1)(m), C312865 source witness and every frozen evidence entry (zero); no equivalent accepted source exists.",
        "facts": [], "gaps": [gap],
    }
    plan["cases"] = [{
        "case_id": AID + "__" + name, "target_law_id": "NRS-484B-450-1m",
        "activity": activity, "endpoint": endpoint, "exception_probe": exception,
        "gap_ids": [gap["id"]],
        "construction": "source-reviewed highway tunnel, portal and destination with original motor vehicle and other-traffic capture",
        "measurement": "Original full-body footprint versus surveyed tunnel boundary, speed/activity interval, other traffic and authority sources; judgment unresolved",
        "physical_risk": {"status": "physical", "reason": "Tunnel lighting, interior route clearance and four-view body/portal visibility require original Native readback."},
    } for name, activity, endpoint, exception in KINDS]
    ids = {name: AID + "__" + name for name, *_ in KINDS}
    fixed = [
        "same source-reviewed C312865 highway tunnel, portals and map geometry",
        "same ego and other-vehicle blueprints, approach, weather, camera views, 20 Hz and duration",
        "same controller except declared destination, activity or exception context",
    ]
    pairs = (
        ("portal_location", "outside_stop", "inside_stop", "destination outside versus inside surveyed tunnel"),
        ("activity_stand", "inside_stop", "inside_stand", "requested and observed stop versus stand activity"),
        ("activity_park", "inside_stop", "inside_park", "requested and observed stop versus park activity"),
        ("necessary_conflict", "inside_stop", "inside_conflict", "other vehicle path and necessity evidence"),
        ("law_direction", "inside_stop", "inside_law", "law compliance source and direction"),
        ("police_direction", "inside_stop", "inside_police", "police identity and direction"),
        ("official_device", "inside_stop", "inside_device", "official device identity, state and direction"),
    )
    plan["comparisons"] = [{
        "comparison_id": label, "case_ids": [ids[left], ids[right]],
        "fixed_conditions": fixed,
        "deliberate_differences": [difference],
        "legal_limit": "A measured halt or direction source does not by itself determine statutory necessity or compliance.",
    } for label, left, right, difference in pairs]
    plan["requirement_dispositions"] = [{
        "requirement": "NRS 484B.450(1)(m) tunnel stop, stand, park and traffic/law/police/device exceptions",
        "source": "inputs/" + AID + "/assignment.json",
        "status": "selected_required",
        "evidence_or_gap": "Eight original captures and seven controlled comparisons; no accepted recording.",
        "case_ids": [case["case_id"] for case in plan["cases"]],
    }]
    plan["source_observation_mapping"] = {}
    plan["observations"] = [{"name": name, "mandatory": True,
                              "description": "Original source-bound " + name.replace("_", " ")}
                             for name in ("highway_status", "tunnel_boundary", "ego_body_footprint",
                                          "ego_speed", "halt_activity", "other_vehicle_motion",
                                          "other_vehicle_purpose", "exception_authority")]
    plan["camera_plan"] = {"profile": "overview1080-capability", "duration_s": 45,
                           "composition": "synchronized_four_view_primary", "coverage": [
        {"view": "overview", "subject": "both portals, approach, tunnel and both vehicles", "interval": "complete operation"},
        {"view": "approach", "subject": "ego and entry portal", "interval": "approach through halt"},
        {"view": "tunnel_reference", "subject": "ego full body and tunnel boundary", "interval": "approach through halt"},
        {"view": "driver_reference", "subject": "ego control and other vehicle", "interval": "complete operation"},
    ]}
    plan["runtime_uncertainties"] = [
        "Actual tunnel highway status, full-body placement and camera visibility require original Native review.",
        "Traffic-conflict necessity and law, police or official-device authority require independent source and legal review.",
    ]
    plan["planning_status"] = "selected_tunnel_branch_construction_in_progress"
    path.write_text(json.dumps(plan, indent=2, ensure_ascii=False) + "\n")
    print(f"planned {len(plan['cases'])} exact cases and {len(plan['comparisons'])} comparisons")


if __name__ == "__main__":
    main()
