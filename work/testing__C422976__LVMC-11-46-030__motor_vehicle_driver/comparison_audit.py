"""Independent exact-case fixed-condition and measured-difference audit."""

import json
from pathlib import Path

from package_contract import LAW


HERE = Path(__file__).resolve().parent
EXPECTED = {
    "stop_51_vs_50": {"stop_distance_target_ft"},
    "stop_51_vs_49": {"stop_distance_target_ft"},
    "go_vs_wait": {"release_kind", "ego_response"},
    "go_vs_departure": {"release_kind"},
    "go_vs_premature": {"release_kind", "ego_response"},
    "human_vs_device": {"warning_kind", "release_kind"},
    "warning_vs_no_warning": {"warning_kind", "release_kind", "ego_response", "stop_distance_target_ft"},
    "child_warning_vs_presence": {"warning_kind", "release_kind", "ego_response"},
}


def definitions():
    proposal = json.loads((HERE / "proposals/cases.json").read_text())
    cases = {case["case_id"]: case for case in proposal["cases"] if case.get("target_law_id") == LAW}
    comparisons = {item["comparison_id"]: item for item in proposal["comparisons"]}
    return cases, comparisons


def audit(comparison_id, left, right):
    cases, comparisons = definitions()
    pair = comparisons.get(comparison_id)
    if pair is None or [left.get("case_id"), right.get("case_id")] != pair["case_ids"]:
        raise ValueError("exact selected school-lane comparison required")
    for receipt in (left, right):
        if (receipt.get("format") != "c422976-original-delivery-audit-v1" or
                receipt.get("source_kind") != "original_native_attempt" or
                receipt.get("frames_checked") != 900 or
                receipt.get("physical_completion") != "requires independent local review"):
            raise ValueError("original audited school-lane receipt required")
    if (left.get("attempt_id") == right.get("attempt_id") or
            left.get("trace_sha256") == right.get("trace_sha256")):
        raise ValueError("comparison reuses an original motion attempt")
    if left.get("site_sha256") != right.get("site_sha256"):
        raise ValueError("reviewed school-lane site changed across comparison")
    values = []
    for receipt in (left, right):
        assignments = cases[receipt["case_id"]]["variable_assignments"]
        values.append({name: item["value"] for name, item in assignments.items()})
    differences = {name for name in values[0] if values[0][name] != values[1][name]}
    expected = EXPECTED.get(comparison_id)
    if expected is None:
        if not comparison_id.startswith("sweep_"):
            raise ValueError("unassigned school-lane comparison")
        expected = set(pair["deliberate_differences"])
    if differences != expected:
        raise ValueError("requested comparison variable isolation differs: " + comparison_id)
    for receipt in (left, right):
        measurement = receipt.get("measurement", {})
        if not isinstance(measurement.get("stop"), dict) or not isinstance(
                measurement.get("warning"), dict) or not isinstance(measurement.get("release"), dict):
            raise ValueError("original stop, warning and release measurements required")
    return {"format": "c422976-original-comparison-v1",
            "comparison_id": comparison_id, "case_ids": pair["case_ids"],
            "original_attempt_ids": [left["attempt_id"], right["attempt_id"]],
            "fixed_site_sha256": left["site_sha256"],
            "requested_differences": sorted(differences),
            "original_measurements_retained": True,
            "physical_acceptance": False, "legal_verdict": "unresolved"}
