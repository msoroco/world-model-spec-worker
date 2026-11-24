"""Check the exact partial dispatch packet and reject missing coverage."""
from __future__ import annotations

import copy
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def validate(packet: dict) -> None:
    plan = json.loads((ROOT / "case-plan.json").read_text())
    expected_cases = {item["case_id"] for item in plan["cases"]}
    expected_pairs = {item["comparison_id"] for item in plan["comparisons"]}
    cases = packet.get("cases", [])
    comparisons = packet.get("comparison_audit_commands", [])
    if (len(cases) != len(expected_cases) or
            {row.get("case_id") for row in cases} != expected_cases):
        raise ValueError("exact case queue coverage changed")
    if (len(comparisons) != len(expected_pairs) or
            {row.get("comparison_id") for row in comparisons} != expected_pairs):
        raise ValueError("exact comparison queue coverage changed")
    for row in cases:
        case = row["case_id"]
        for key in ("capture_command", "postprocessing_command", "owner_release_command",
                    "additional_source_audit_command", "prepare_command", "execute_command",
                    "accept_command"):
            if case not in row.get(key, ""):
                raise ValueError("case command missing exact ID: " + key)
        if ("--pixel-review" not in row["additional_source_audit_command"] or
                "--physical-receipt" not in row["additional_source_audit_command"] or
                "--candidate fallback1" not in row["candidate_commands"]["fallback1"]):
            raise ValueError("delivery audit or fallback command incomplete")
        audit_command = row["additional_source_audit_command"]
        profile = "/original_media_profile.py --attempt \"$ATTEMPT\" --output \"${AUDIT}.media-profile.json\""
        independent = "/independent/delivery_audit.py --case-id " + case
        if profile not in audit_command or independent not in audit_command or audit_command.index(profile) > audit_command.index(independent) or " && " not in audit_command:
            raise ValueError("original camera profile must precede independent delivery audit")
    for row in comparisons:
        if (row["comparison_id"] not in row["command"] or
                "--baseline-attempt" not in row["command"] or
                "--changed-attempt" not in row["command"]):
            raise ValueError("comparison audit command incomplete")


def main() -> None:
    packet = json.loads((ROOT / "queue-entries.partial.json").read_text())
    validate(packet)
    missing = copy.deepcopy(packet)
    missing["cases"].pop()
    try:
        validate(missing)
    except ValueError as error:
        if "exact case queue coverage changed" not in str(error):
            raise
    else:
        raise AssertionError("missing exact case was accepted")
    missing_pair = copy.deepcopy(packet)
    missing_pair["comparison_audit_commands"].pop()
    try:
        validate(missing_pair)
    except ValueError as error:
        if "exact comparison queue coverage changed" not in str(error):
            raise
    else:
        raise AssertionError("missing exact comparison was accepted")
    missing_profile = copy.deepcopy(packet)
    missing_profile["cases"][0]["additional_source_audit_command"] = missing_profile["cases"][0]["additional_source_audit_command"].split(" && ", 1)[1]
    try:
        validate(missing_profile)
    except ValueError as error:
        if "original camera profile must precede" not in str(error):
            raise
    else:
        raise AssertionError("missing original camera profile was accepted")
    print("four exact cases and two comparison commands pass; missing rows rejected")


if __name__ == "__main__":
    main()
