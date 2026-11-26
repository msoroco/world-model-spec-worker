"""Check source and protocol isolation across original one-way parking cases."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from one_way_side_observations import observe
from street_scene_construction import ASSIGNMENT, load_case


BASE = "park_left_notice"
VARIABLES = {
    "stand_left_notice": ("activity_request",),
    "park_right_notice": ("vehicle_side_request",),
    "park_left_no_notice": ("notice_request",),
    "park_left_outside_notice_extent": ("notice_request",),
    "park_left_two_way": ("street_direction_request",),
    "travel_left_notice": ("activity_request",),
    "temporary_halt_left_notice": ("activity_request",),
    "park_left_notice_reverse_geometry": ("street_direction_request",),
}
FIXED_SOURCES = ("street_legal_status_source", "street_boundary_source",
                 "public_access_source", "city_limits_source",
                 "person_identity_source", "vehicle_identity_source")


def audit(comparison: str, left: dict, right: dict) -> dict:
    if comparison not in VARIABLES:
        raise ValueError("unknown exact one-way parking comparison")
    cases = [load_case(ASSIGNMENT + "__" + name) for name in (BASE, comparison)]
    packets = [left, right]
    observations = []
    contexts = []
    for packet, case in zip(packets, cases):
        if packet.get("case_id") != case["case_id"]:
            raise ValueError("comparison exact case identity mismatch")
        context = Path(packet["context"])
        trace = Path(packet["trace"])
        receipt = Path(packet["receipt"])
        observations.append(observe(case["case_id"], context, trace, receipt))
        contexts.append(json.loads(context.read_text()))
    if len(observations[0]["samples"]) != 900 or len(observations[1]["samples"]) != 900:
        raise ValueError("comparison requires two complete original 45 s traces")
    for name in ("camera_plan_sha256", "duration_frames") + FIXED_SOURCES:
        if contexts[0].get(name) is None or contexts[0].get(name) != contexts[1].get(name):
            raise ValueError("fixed source/protocol differs: " + name)
    if comparison != "park_left_notice_reverse_geometry":
        if contexts[0].get("permitted_direction_centerline_xy_m") != contexts[1].get("permitted_direction_centerline_xy_m"):
            raise ValueError("fixed permitted direction geometry differs")
    for name in ("activity_request", "vehicle_side_request", "notice_request",
                 "street_direction_request"):
        if name not in VARIABLES[comparison] and cases[0][name] != cases[1][name]:
            raise ValueError("undeclared case intervention differs: " + name)
    key = VARIABLES[comparison][0]
    if cases[0][key] == cases[1][key]:
        raise ValueError("declared case intervention does not differ")
    return {"assignment_id": ASSIGNMENT, "comparison_id": comparison,
            "case_ids": [case["case_id"] for case in cases],
            "original_receipt_sha256": [hashlib.sha256(Path(packet["receipt"]).read_bytes()).hexdigest()
                                        for packet in packets],
            "fixed_sources_and_protocol_checked": True,
            "review_limit": "Software isolation does not establish standing, parking, left side or notice legality."}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--comparison", choices=tuple(VARIABLES), required=True)
    parser.add_argument("--left", type=Path, required=True)
    parser.add_argument("--right", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = audit(args.comparison, json.loads(args.left.read_text()),
                   json.loads(args.right.read_text()))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
