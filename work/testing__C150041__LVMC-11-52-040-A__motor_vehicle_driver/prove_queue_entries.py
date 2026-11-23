"""Reject missing C150041 case, comparison, candidate and audit commands."""
from __future__ import annotations

import copy
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def validate(packet: dict) -> None:
    plan = json.loads((ROOT / "case-plan.json").read_text())
    cases = packet.get("cases", [])
    comparisons = packet.get("comparison_audit_commands", [])
    if (len(cases) != 6 or
            {entry["case_id"] for entry in cases} !=
            {entry["case_id"] for entry in plan["cases"]}):
        raise ValueError("exact case queue coverage changed")
    if (len(comparisons) != 4 or
            {entry["comparison_id"] for entry in comparisons} !=
            {entry["comparison_id"] for entry in plan["comparisons"]}):
        raise ValueError("exact comparison queue coverage changed")
    for row in cases:
        case = row["case_id"]
        for key in ("prepare_command", "execute_command", "capture_command",
                    "owner_release_command", "postprocessing_command",
                    "additional_source_audit_command", "accept_command"):
            if case not in row.get(key, ""):
                raise ValueError("case command missing exact identity: " + key)
        if (set(row.get("candidate_commands", {})) != {"fallback1"} or
                any(case not in command or "--candidate " + candidate not in command
                    for candidate, command in row["candidate_commands"].items()) or
                "--pixel-review" not in row["additional_source_audit_command"] or
                "--physical-receipt" not in row["additional_source_audit_command"]):
            raise ValueError("candidate or independent case audit omitted")
    for row in comparisons:
        command = row.get("command", "")
        if (row["comparison_id"] not in command or
                any(flag not in command for flag in ("--baseline-attempt", "--changed-attempt",
                                                   "--baseline-delivery", "--changed-delivery"))):
            raise ValueError("original comparison command incomplete")


def main() -> None:
    packet = json.loads((ROOT / "queue-entries.partial.json").read_text())
    validate(packet)
    for section, message in (("cases", "exact case queue coverage changed"),
                             ("comparison_audit_commands", "exact comparison queue coverage changed")):
        changed = copy.deepcopy(packet)
        changed[section].pop()
        try:
            validate(changed)
        except ValueError as error:
            if str(error) != message:
                raise
        else:
            raise AssertionError("missing " + section + " row accepted")
    changed = copy.deepcopy(packet)
    changed["cases"][0]["candidate_commands"].pop("fallback1")
    try:
        validate(changed)
    except ValueError as error:
        if str(error) != "candidate or independent case audit omitted":
            raise
    else:
        raise AssertionError("missing fallback command accepted")
    print("six exact case and four comparison commands pass; missing rows/fallback rejected")


if __name__ == "__main__":
    main()
