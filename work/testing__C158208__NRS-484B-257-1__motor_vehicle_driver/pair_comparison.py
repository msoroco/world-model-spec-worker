"""Independent source-bound audit for the two nearest-view yield responses.

The audit compares engineering observables. It does not decide legal compliance.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from nearest_view_measurement import measure
from physical_completion import assess
from source_tick_capture import verify_seal


ASSIGNMENT = "testing__C158208__NRS-484B-257-1__motor_vehicle_driver"
CASES = (ASSIGNMENT + "__nearest_view_response",
         ASSIGNMENT + "__nearest_view_uninterrupted")


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _hex(value: str, label: str) -> str:
    if not isinstance(value, str) or len(value) != 64 or any(c not in "0123456789abcdef" for c in value):
        raise ValueError(f"{label} must be a SHA256 hex digest")
    return value


def _load(attempt: Path, expected_case: str, *, diagnostic: bool,
          expected: dict | None) -> dict:
    attempt = Path(attempt)
    identity = json.loads((attempt / "capture-identity.json").read_text(encoding="utf-8"))
    if identity.get("format") != "c158208-original-capture-identity-v1":
        raise ValueError("capture identity format differs")
    if identity.get("assignment_id") != ASSIGNMENT or identity.get("case_id") != expected_case:
        raise ValueError("capture identity case differs")
    if identity.get("provenance_kind") != ("synthetic_fixture" if diagnostic else "original_capture"):
        raise ValueError("capture provenance differs")
    construction = _hex(identity.get("construction_sha256"), "construction hash")
    _hex(identity.get("site_packet_sha256"), "site packet hash")
    _hex(identity.get("map_opendrive_sha256"), "map hash")
    if not diagnostic:
        if not isinstance(expected, dict):
            raise ValueError("original capture requires independently reviewed expected hashes")
        for field in ("construction_sha256", "site_packet_sha256", "map_opendrive_sha256"):
            if identity[field] != _hex(expected.get(field), f"expected {field}"):
                raise ValueError(f"capture identity {field} differs from reviewed expectation")
    if identity.get("original_tick_seal_sha256") != _sha(attempt / "nearest-view-tick-seal.json"):
        raise ValueError("capture identity tick seal hash differs")
    packet = verify_seal(attempt)
    if not diagnostic and len(packet["samples"]) != 900:
        raise ValueError("original capture requires 900 contiguous 20 Hz frames")
    measured = measure(packet)
    completion = assess(attempt, expected_case, construction, diagnostic_fixture=diagnostic)
    if not completion["maneuver_completed"]:
        raise ValueError("original body did not complete intersection traversal")
    return {"identity": identity, "packet": packet, "measured": measured,
            "completion": completion, "identity_sha256": _sha(attempt / "capture-identity.json")}


def audit(response_attempt: Path, uninterrupted_attempt: Path, *, diagnostic: bool = False,
          reviewed_expectations: dict | None = None) -> dict:
    if not diagnostic and (not isinstance(reviewed_expectations, dict)
                           or set(reviewed_expectations) != set(CASES)):
        raise ValueError("original pair requires exact reviewed case expectations")
    response = _load(response_attempt, CASES[0], diagnostic=diagnostic,
                     expected=(reviewed_expectations or {}).get(CASES[0]))
    uninterrupted = _load(uninterrupted_attempt, CASES[1], diagnostic=diagnostic,
                          expected=(reviewed_expectations or {}).get(CASES[1]))
    a, b = response["identity"], uninterrupted["identity"]
    for field in ("site_packet_sha256", "map_opendrive_sha256"):
        if a[field] != b[field]:
            raise ValueError(f"fixed {field} differs across comparison")
    if response["packet"]["geometry"] != uninterrupted["packet"]["geometry"]:
        raise ValueError("fixed intersection geometry differs across comparison")
    if response["packet"]["reviewed_context"] != uninterrupted["packet"]["reviewed_context"]:
        raise ValueError("fixed reviewed context differs across comparison")
    left = response["measured"]
    right = uninterrupted["measured"]
    if left["through_vehicle_history"] != right["through_vehicle_history"]:
        raise ValueError("through vehicle history differs across comparison")
    if left["first_view"] != right["first_view"] or left["intersection_entry"] != right["intersection_entry"]:
        raise ValueError("viewpoint or entry timing differs across comparison")
    left_speed = left["minimum_approach_speed_mps"]
    right_speed = right["minimum_approach_speed_mps"]
    if not left_speed < right_speed:
        raise ValueError("response did not realize lower approach speed")
    return {"comparison_id": "yield_nearest_view", "case_ids": list(CASES),
            "status": "diagnostic_fixture_only" if diagnostic else "source_bound_motion_only",
            "fixed_conditions_checked": ["site packet", "OpenDRIVE map", "intersection geometry",
                                         "reviewed context", "through vehicle history",
                                         "viewpoint and entry timing"],
            "realized_speed_mps": {CASES[0]: left_speed, CASES[1]: right_speed},
            "sources": [{"case_id": CASES[0], "capture_identity_sha256": response["identity_sha256"]},
                        {"case_id": CASES[1], "capture_identity_sha256": uninterrupted["identity_sha256"]}],
            "video_accepted": False, "legal_status": "unresolved"}


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--response-attempt", required=True, type=Path)
    parser.add_argument("--uninterrupted-attempt", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--diagnostic-fixture", action="store_true")
    parser.add_argument("--reviewed-expectations", type=Path)
    args = parser.parse_args()
    expectations = json.loads(args.reviewed_expectations.read_text(encoding="utf-8")) \
        if args.reviewed_expectations else None
    result = audit(args.response_attempt, args.uninterrupted_attempt,
                   diagnostic=args.diagnostic_fixture,
                   reviewed_expectations=expectations)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(result["status"])
