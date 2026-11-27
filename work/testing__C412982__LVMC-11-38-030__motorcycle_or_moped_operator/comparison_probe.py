"""CPU unit fixtures for independent comparison rejection branches."""
from __future__ import annotations
import copy
from comparison_audit import AID, GROUPS, audit_group


def report(suffix):
    device = "motor_scooter" if suffix.startswith("motor_scooter") else "motorcycle"
    surface = "road" if suffix.endswith("road") else "sidewalk"
    municipality = "North Las Vegas" if suffix.endswith("outside_city") else "Las Vegas"
    return {"format": "worker-delivery-audit", "passed": True,
            "protocol_fixture_checked": False, "physical_acceptance_claimed": True,
            "case_id": AID + "__" + suffix, "frame_count": 900,
            "comparison_record": {"source_kind": "original_native_capture",
                                  "fixed_source_sha256": {"native_map": "unit-only"},
                                  "municipal_boundary_source_sha256": "unit-only",
                                  "camera_plan": ["four-view-unit-only"],
                                  "duration_s": 45, "frame_count": 900,
                                  "device_kind": device,
                                  "operator_conduct": "walking" if "walking" in suffix else "riding",
                                  "surface": surface,
                                  "side": "south" if suffix.endswith("south") else "north",
                                  "municipality": municipality,
                                  "sidewalk_center_frames": 0 if surface == "road" else 900,
                                  "road_center_frames": 900 if surface == "road" else 0,
                                  "sidewalk_body_overlap_frames": 0 if surface == "road" else 900,
                                  "road_body_overlap_frames": 900 if surface == "road" else 0}}


def main():
    for comparison_id, suffixes in GROUPS.items():
        reports = {AID + "__" + suffix: report(suffix) for suffix in suffixes}
        answer = audit_group(comparison_id, reports)
        if not answer["physical_comparison_passed"] or answer["legal_verdict_claimed"]:
            raise ValueError("comparison unit fixture misclassified")
        changed = copy.deepcopy(reports)
        changed[AID + "__" + suffixes[1]]["comparison_record"]["camera_plan"] = ["changed"]
        try:
            audit_group(comparison_id, changed)
        except ValueError as error:
            if "changed fixed original condition" not in str(error):
                raise
        else:
            raise ValueError("changed fixed camera plan accepted")
        changed = copy.deepcopy(reports)
        changed[AID + "__" + suffixes[1]]["passed"] = False
        try:
            audit_group(comparison_id, changed)
        except ValueError as error:
            if "original accepted report required" not in str(error):
                raise
        else:
            raise ValueError("nonaccepted report accepted")
        print(comparison_id, "positive_unit_fixture", "changed_fixed_source_rejected",
              "nonaccepted_report_rejected")


if __name__ == "__main__":
    main()
