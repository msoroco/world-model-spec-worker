"""Independent, saved-only provenance and physical target audit."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from analysis import SOURCES, build_report


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def audit(attempt, *, diagnostic_test=False):
    root = Path(attempt)
    report = build_report(root)
    result = json.loads((root/"result.json").read_text())
    seal = json.loads((root/"capture-seal.json").read_text())
    provenance = json.loads((root/"acquisition-provenance.json").read_text())
    kind = "synthetic_fixture" if diagnostic_test else "native"
    marked = bool(diagnostic_test)
    if (seal.get("format") != "worker-sealed-capture" or
            seal.get("provenance_kind") != kind or
            seal.get("diagnostic_fixture") is not marked or
            seal.get("restoration",{}).get("restored") is not True or
            provenance.get("provenance_kind") != kind or
            provenance.get("diagnostic_fixture") is not marked or
            (diagnostic_test and (result.get("provenance_kind") != kind or
                                  result.get("diagnostic_fixture") is not True))):
        raise ValueError("Native sealed capture and restoration proof required" if not diagnostic_test
                         else "Synthetic diagnostic seal and restoration proof required")
    if any(k in result for k in ("legal_verdict","compliant","violating")):
        raise ValueError("delivery result contains legal verdict")
    originals = (*SOURCES,"overview.mkv","approach.mkv","reference_corner.mkv",
                 "driver_reference.mkv")
    for name in originals:
        path = root/name
        if not path.is_file() or not path.stat().st_size:
            raise ValueError("missing original delivery source: "+name)
        digest = seal.get("sources",{}).get(name)
        if digest is None:
            raise ValueError("capture seal omits original source: "+name)
        # The pinned sealer's tree records a SHA digest for every original source.
        if isinstance(digest,str) and digest != sha(path):
            raise ValueError("sealed original source changed: "+name)
    observed = report["measurements"]["median_uturn_measurement"]["value"]
    config = json.loads((root/"config.json").read_text())
    if result.get("case_id") != config.get("selected_case_id"):
        raise ValueError("delivery result differs from exact case config")
    closed_approach = config["case"].get("physical_target") == "closed_divider_approach"
    wrong_roadway = config["case"].get("physical_target") == "non_right_roadway"
    no_turn = config["case"].get("physical_target") == "source_right_roadway_continuation"
    if result.get("measured_values") != observed:
        raise ValueError("result measurements differ from original saved geometry")
    targets = {item.get("target"):item for item in result.get("target_checks",[])}
    if no_turn:
        stayed = (observed["source_right_roadway_all_frames"] and
                  observed["source_right_roadway_final_occupancy"] and
                  not observed["opening_contact_frames"] and
                  not observed["closed_divider_contact_frames"] and
                  not observed["u_turn_orientation_observed"] and
                  not observed["destination_right_roadway_departure_observed"])
        expected = (("source right roadway continued without turn",stayed),)
    elif wrong_roadway:
        reached_wrong = (observed["non_right_roadway_final_occupancy"] and
                         bool(observed["opening_full_body_frames"]) and
                         any(item["through_opening"] for item in
                             observed["roadway_centerline_crossings"]) and
                         not observed["closed_divider_contact_frames"] and
                         not observed["destination_right_roadway_departure_observed"])
        expected = (("non-right roadway reached through opening",reached_wrong),
                    ("destination right roadway not reached",
                     observed["destination_right_roadway_departure_observed"]))
    elif closed_approach:
        clearance = observed["final_closed_divider_clearance_m"]
        expected = (("closed-divider approach with full-body clearance",
                     not observed["opening_contact_frames"] and
                     not observed["closed_divider_contact_frames"] and
                     0 < clearance <= 1.0),
                    ("destination right roadway not reached",
                     observed["destination_right_roadway_departure_observed"]))
    else:
        expected = (("realized multiple-movement U-turn",observed["multiple_movement_observed"]),
                    ("full-body opening crossing without closed-divider contact",
                     observed["engineering_crossing_observed"]))
    for label, value in expected:
        if label not in targets or targets[label].get("measured") is not value:
            raise ValueError("physical target lacks matching saved evidence: "+label)
    required_states = (("behavior_attempted","maneuver_completed") if diagnostic_test else
                       ("setup_confirmed","behavior_attempted","maneuver_completed"))
    if not all(result.get(key) is True for key in required_states):
        raise ValueError("physical setup, attempt or maneuver not confirmed")
    if not all(item.get("matched") is True for item in targets.values()):
        raise ValueError("declared original physical target not matched")
    if no_turn:
        if not expected[0][1]:
            raise ValueError("original no-turn roadway continuation absent")
    elif wrong_roadway:
        if not expected[0][1] or expected[1][1]:
            raise ValueError("original non-right roadway occupancy absent")
    elif closed_approach:
        if (not expected[0][1] or expected[1][1] or
                observed["engineering_crossing_observed"]):
            raise ValueError("original safe closed-divider approach absent")
    elif not observed["engineering_crossing_observed"] or not observed["u_turn_orientation_observed"]:
        raise ValueError("original opening crossing or U-turn orientation absent")
    return {"delivery_physical_audit_passed":not diagnostic_test,
            "diagnostic_audit_test_passed":diagnostic_test,
            "legal_verdict_claimed":False,
            "source_hashes":{name:sha(root/name) for name in originals}}
