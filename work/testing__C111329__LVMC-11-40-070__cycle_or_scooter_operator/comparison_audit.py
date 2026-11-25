"""Independent source-bound comparison of device instructions and exception."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from saved_instruction import measure
from delivery_audit import audit_attempt_sources


def audit_from_sources(comparison: dict, cases: dict, site_path: Path,
                       site_sha256: str, trace_sources: dict, *, diagnostic: bool = False) -> dict:
    """Recompute each response from sealed original traces before comparison.

    This does not make a physical or legal acceptance claim. The separate camera
    audit must decode the original four-camera bodies before delivery review.
    """
    raw = Path(site_path).read_bytes()
    if hashlib.sha256(raw).hexdigest() != site_sha256:
        raise ValueError("site source hash mismatch")
    site = json.loads(raw)
    if site.get("diagnostic_fixture") and not diagnostic:
        raise ValueError("diagnostic site cannot establish original comparison")
    measurements = []
    for case_id in comparison["case_ids"]:
        case = cases[case_id]
        trace_path, trace_sha256 = trace_sources[case_id]
        if json.loads(Path(trace_path).read_text()).get("diagnostic_fixture") and not diagnostic:
            raise ValueError("diagnostic trace cannot establish original comparison")
        value = measure(Path(trace_path), trace_sha256, case, site, site_sha256)
        value["context"] = {
            "map_name": site["map_name"],
            "jurisdiction_source": site["jurisdiction_source"],
            "governed_approach": site["governed_approach"],
            "bike_blueprint_id": site["bike_blueprint_id"],
            "route": site["vehicle_route"],
            "camera_contract": site["camera_contract"],
            "duration_s": 45,
            "device_authority_source": site["device_authority_source"],
            "vehicle_applicability_source": site["vehicle_applicability_source"],
            "device_type": case["device_type"],
            "device_instruction": case["device_instruction"],
            "officer_direction": case["officer_direction"],
        }
        measurements.append(value)
    result = audit(comparison, *measurements)
    result["source_hashes"] = {case_id: measurements[i]["source_hashes"]
                               for i, case_id in enumerate(comparison["case_ids"])}
    result["diagnostic_fixture"] = diagnostic
    result["physical_acceptance"] = False
    return result


def audit(comparison: dict, left: dict, right: dict) -> dict:
    if [left.get("case_id"), right.get("case_id")] != comparison["case_ids"]:
        raise ValueError("comparison case identity mismatch")
    for row in (left, right):
        if row.get("source_kind") != "original_native" or row.get("legal_assessment") != "unresolved":
            raise ValueError("missing original measurement or legal separation")
        if not row.get("device_id") or not row.get("bike_id"):
            raise ValueError("missing participant or device identity")
        if (row.get("format") != "c111329-saved-instruction-measurement"
                or "crossing_frame" not in row or "hold_window_frames" not in row
                or "device_state_at_response" not in row
                or "officer_command_at_response" not in row):
            raise ValueError("incomplete saved response measurement")
        if (row["crossing_frame"] is None) == (row["hold_window_frames"] is None):
            raise ValueError("ambiguous original movement response")
        if (not row.get("context") or not row.get("source_hashes", {}).get("site")
                or not row.get("source_hashes", {}).get("trace")):
            raise ValueError("missing source-bound context")
    variable = comparison["deliberate_variable"]
    if variable not in {"operator_motion", "device_instruction", "officer_direction", "device_type"}:
        raise ValueError("unknown deliberate variable")
    fields = ("map_name", "jurisdiction_source", "governed_approach", "bike_blueprint_id", "route", "camera_contract", "duration_s", "device_authority_source", "vehicle_applicability_source", "device_type", "device_instruction", "officer_direction")
    for field in fields:
        if field == variable or (variable == "device_type" and field in {"device_authority_source", "vehicle_applicability_source", "device_instruction"}):
            continue
        if left["context"].get(field) != right["context"].get(field):
            raise ValueError("fixed condition changed: " + field)
    observed = {"operator_motion": "crossing_frame", "device_instruction": "device_state_at_response", "officer_direction": "officer_command_at_response", "device_type": "device_id"}[variable]
    if left.get(observed) == right.get(observed):
        raise ValueError("declared variable did not differ: " + variable)
    if left["source_hashes"]["site"] != right["source_hashes"]["site"] and variable != "device_type":
        raise ValueError("site source changed")
    return {"format": "c111329-device-comparison-audit", "comparison_id": comparison["comparison_id"], "case_ids": comparison["case_ids"], "passed": True, "legal_assessment": "unresolved"}


def audit_attempts(comparison_id: str, attempts: list[Path]) -> dict:
    """Recompute a selected pair only after both original captures decode."""
    plan = json.loads((Path(__file__).resolve().parent / "case-plan.json").read_text())
    selected = [row for row in plan["comparisons"]
                if row["comparison_id"] == comparison_id]
    if len(selected) != 1 or len(attempts) != len(selected[0]["case_ids"]):
        raise ValueError("selected comparison attempt count differs")
    cases = {row["case_id"]: row for row in plan["cases"]}
    checked = [audit_attempt_sources(Path(path), cases[case_id]) for path, case_id in
               zip(attempts, selected[0]["case_ids"])]
    if len({row["site_sha256"] for row in checked}) != 1:
        raise ValueError("fixed original site source differs")
    sources = {case_id: (row["trace_path"], row["trace_sha256"])
               for case_id, row in zip(selected[0]["case_ids"], checked)}
    result = audit_from_sources(selected[0], cases, checked[0]["site_path"],
                                checked[0]["site_sha256"], sources)
    result["original_source_audits"] = [
        {"case_id": case_id, "frame_count": row["frame_count"],
         "camera_decode": row["cameras"], "full_video_decode": row["videos"]}
        for case_id, row in zip(selected[0]["case_ids"], checked)]
    return result


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--comparison", required=True)
    parser.add_argument("--attempt", required=True, action="append", type=Path)
    args = parser.parse_args()
    print(json.dumps(audit_attempts(args.comparison, args.attempt), sort_keys=True))
