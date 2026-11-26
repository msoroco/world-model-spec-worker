"""Independent exact-case fixed-site and measured-difference comparison audit."""

import json
from pathlib import Path

from package_contract import LAW

HERE = Path(__file__).resolve().parent
EXPECTED = {
    "core_vs_qualified_hov": {"hov_designation_request", "hov_compliance_request"},
    "core_vs_ineligible_hov": {"hov_designation_request", "hov_compliance_request"},
    "core_vs_inactive_hov": {"hov_designation_request"},
    "core_vs_speed_at_limit": {"ego_speed_request"},
    "core_vs_no_faster_rear": {"rear_encounter_request"},
    "core_vs_move_right": {"ego_response_request"},
    "core_vs_city_boundary": {"exception_context_request"},
    "core_vs_hazard_necessity": {"exception_context_request"},
    "sweep_sign_exposure": {"sign_exposure_start_s"},
    "sweep_rear_speed_delta": {"rear_speed_delta_target_mps"},
    "sweep_hov_occupancy": {"hov_occupancy_target"},
}


def definitions():
    proposal = json.loads((HERE / "proposals/cases.json").read_text())
    cases = {case["case_id"]: case for case in proposal["cases"] if case.get("target_law_id") == LAW}
    comparisons = {item["comparison_id"]: item for item in proposal["comparisons"]}
    return cases, comparisons


def audit(comparison_id, *receipts):
    cases, comparisons = definitions()
    pair = comparisons.get(comparison_id)
    if pair is None or [r.get("case_id") for r in receipts] != pair["case_ids"]:
        raise ValueError("exact selected left-lane/HOV comparison required")
    if len(receipts) not in (2, 3):
        raise ValueError("two or three selected comparison members required")
    for receipt in receipts:
        if (receipt.get("format") != "c380107-original-delivery-audit-v1" or
                receipt.get("source_kind") != "original_native_attempt" or
                receipt.get("frames_checked") != 900 or
                receipt.get("physical_completion") != "requires independent local review"):
            raise ValueError("original audited highway/HOV receipt required")
    if len({r.get("attempt_id") for r in receipts}) != len(receipts) or len(
            {r.get("trace_sha256") for r in receipts}) != len(receipts):
        raise ValueError("comparison reuses an original motion attempt")
    if len({r.get("site_sha256") for r in receipts}) != 1:
        raise ValueError("reviewed controlled-access site changed across comparison")
    values = [{name: item["value"] for name, item in cases[receipt["case_id"]]["variable_assignments"].items()}
              for receipt in receipts]
    differences = {name for name in values[0] if len({str(v[name]) for v in values}) > 1}
    if differences != EXPECTED[comparison_id]:
        raise ValueError("requested comparison variable isolation differs: " + comparison_id)
    for receipt in receipts:
        measurement = receipt.get("measurement", {})
        required = ("rear_gap_crossing_frame", "posted_limit_mps", "extreme_left_lane_id",
                    "hov_designation_state", "hov_compliance_state")
        if not all(key in measurement for key in required):
            raise ValueError("original source-bound rear/HOV measurements required")
    return {"format": "c380107-original-comparison-v1", "comparison_id": comparison_id,
            "case_ids": pair["case_ids"], "original_attempt_ids": [r["attempt_id"] for r in receipts],
            "fixed_site_sha256": receipts[0]["site_sha256"],
            "requested_differences": sorted(differences),
            "original_measurements": [r["measurement"] for r in receipts],
            "physical_acceptance": False, "legal_verdict": "unresolved"}
