"""In-memory comparison fixtures; never an original capture receipt."""

from __future__ import annotations

import copy

from comparison_audit import AID, GROUPS, audit_group
from signed_road import BY_SUFFIX


def report(suffix):
    case = BY_SUFFIX[suffix]
    return {"format": "worker-delivery-audit", "passed": True,
            "protocol_fixture_checked": False,
            "physical_acceptance_claimed": True,
            "case_id": AID + "__" + suffix, "frame_count": 900,
            "comparison_record": {
                "source_kind": "original_native_capture",
                "fixed_source_sha256": {"native_map": "unit-only"},
                "camera_plan": ["four-view-unit-only"], "duration_s": 45,
                "frame_count": 900, "requested_relation": suffix,
                "device_kind": case.device_kind,
                "operator_conduct": case.conduct,
                "surface": "roadway", "extent": case.extent,
                "movement": case.movement, "sign_state": case.sign_state,
                "roadway_center_frames": 900}}


def main():
    for comparison_id, suffixes in GROUPS.items():
        reports = {AID + "__" + suffix: report(suffix) for suffix in suffixes}
        answer = audit_group(comparison_id, reports)
        if not answer["physical_comparison_passed"] or answer["legal_verdict_claimed"]:
            raise ValueError("comparison unit fixture misclassified")
        changed = copy.deepcopy(reports)
        changed[AID + "__" + suffixes[1]]["comparison_record"]["fixed_source_sha256"]["native_map"] = "changed"
        try:
            audit_group(comparison_id, changed)
        except ValueError as error:
            if "changed fixed original condition" not in str(error):
                raise
        else:
            raise ValueError("changed fixed map source accepted")
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
