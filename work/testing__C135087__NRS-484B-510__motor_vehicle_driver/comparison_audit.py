"""Read-only two-attempt comparison with independently pinned site packets."""

from saved_audit import audit as audit_saved
from zone_audit import compare_cases


def audit(left_attempt, right_attempt, left_case, right_case,
          expected_left_site_sha256, expected_right_site_sha256):
    if not expected_left_site_sha256 or not expected_right_site_sha256:
        raise ValueError("independent reviewed site hashes required")
    left = audit_saved(left_attempt, left_case, expected_left_site_sha256)
    right = audit_saved(right_attempt, right_case, expected_right_site_sha256)
    if left["diagnostic_fixture"] or right["diagnostic_fixture"]:
        raise ValueError("diagnostic fixture cannot satisfy original comparison")
    measured = compare_cases(left["source_measurements"], right["source_measurements"])
    return {"case_ids": [left_case, right_case],
            "site_packet_sha256": [expected_left_site_sha256, expected_right_site_sha256],
            "physical_differences": measured["observed_difference"],
            "fixed_context_source_matched": measured["fixed_context_source_matched"],
            "legal_comparison": "unresolved_judgment"}
