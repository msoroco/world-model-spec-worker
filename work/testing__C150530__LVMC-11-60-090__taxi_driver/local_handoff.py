"""Assignment-local CPU proof of the declared post-capture handoff order.

This models receipt dependencies for the exact taxi queue rows. It does not
execute the local worker exchange, release a real resource, or accept a run.
"""
from __future__ import annotations

import json
from pathlib import Path
import shlex

ROOT = Path(__file__).resolve().parent
REQUIRED = ("prepared", "native_exit", "owner_released", "saved_processed",
            "source_audited", "accepted")


def option(command: str, name: str) -> str | None:
    tokens = shlex.split(command)
    positions = [index for index, token in enumerate(tokens) if token == name]
    if len(positions) > 1:
        raise ValueError("duplicate handoff option: " + name)
    return tokens[positions[0] + 1] if positions and positions[0] + 1 < len(tokens) else None


def validate_row(row: dict) -> None:
    case = row["case_id"]
    if row.get("assignment_id") != ROOT.name:
        raise ValueError("wrong assignment")
    for key, verb in (("prepare_command", "prepare-delivery"),
                      ("execute_command", "execute-delivery"),
                      ("accept_command", "accept-delivery")):
        command = row[key]
        if verb not in shlex.split(command) or option(command, "--case") != case:
            raise ValueError("wrong case or stage: " + key)
        if option(command, "--assignment") != ROOT.name or option(command, "--batch") != "full-test-delivery":
            raise ValueError("wrong assignment or batch: " + key)
    for key in ("execute_command", "accept_command"):
        if option(row[key], "--job") != "$JOB_ID" or option(row[key], "--run") != "$RUN":
            raise ValueError("wrong Native job or run: " + key)
    if row["capture_command"] != row["execute_command"]:
        raise ValueError("capture command differs from Native execution")
    if option(row["owner_release_command"], "--attempt") != "$ATTEMPT":
        raise ValueError("owner release lacks exact attempt")
    if option(row["owner_release_command"], "--receipt") != "$OWNER_RELEASE_RECEIPT":
        raise ValueError("owner release receipt differs")
    if option(row["postprocessing_command"], "--case") != case:
        raise ValueError("saved processor selects wrong case")
    if option(row["postprocessing_command"], "--owner-release-receipt") != "$OWNER_RELEASE_RECEIPT":
        raise ValueError("saved processor lacks owner release")
    if (option(row["postprocessing_command"], "--attempt") != "$ATTEMPT"
            or option(row["postprocessing_command"], "--manifest") !=
            f"work/{ROOT.name}/execution-manifest.json"):
        raise ValueError("saved processor attempt or manifest differs")
    if option(row["additional_source_audit_command"], "--case-id") != case:
        raise ValueError("independent auditor selects wrong case")
    if option(row["additional_source_audit_command"], "--case") != case.removeprefix(ROOT.name + "__"):
        raise ValueError("independent auditor selects wrong case suffix")
    if option(row["additional_source_audit_command"], "--pixel-review") != "$PIXEL_REVIEW":
        raise ValueError("independent auditor lacks pixel review")
    if (option(row["additional_source_audit_command"], "--attempt") != "$ATTEMPT"
            or option(row["additional_source_audit_command"], "--job-id") != "$JOB_ID"
            or option(row["additional_source_audit_command"], "--attempt-number") != "$ATTEMPT_NUMBER"
            or option(row["additional_source_audit_command"], "--recording-id") != "$RECORDING_ID"
            or option(row["additional_source_audit_command"], "--physical-receipt") != "$PHYSICAL_RECEIPT"
            or option(row["additional_source_audit_command"], "--output") != "$AUDIT"):
        raise ValueError("independent auditor source or delivery identity differs")
    if option(row["accept_command"], "--audit") != "$AUDIT":
        raise ValueError("acceptance lacks independent audit")
    if option(row["accept_command"], "--attempt") != "$ATTEMPT_NUMBER":
        raise ValueError("acceptance attempt differs")
    if option(row["accept_command"], "--review-archive") != "/external/archive":
        raise ValueError("acceptance archive is not external")


def replay(events: list[dict], case: str) -> dict:
    """Reject missing, duplicated, reordered, cross-attempt or rejected receipts."""
    if [event.get("stage") for event in events] != list(REQUIRED):
        raise ValueError("handoff stages missing, duplicated or reordered")
    identity = None
    for event in events:
        current = (event.get("case_id"), event.get("attempt_id"), event.get("job_id"))
        if current[0] != case or not all(current):
            raise ValueError("handoff identity incomplete or wrong case")
        if identity is None:
            identity = current
        elif current != identity:
            raise ValueError("handoff attempt or job changed")
        if event.get("passed") is not True:
            raise ValueError("handoff stage failed: " + event["stage"])
    return {"case_id": case, "attempt_id": identity[1], "job_id": identity[2],
            "stages": list(REQUIRED), "diagnostic_only": True}


def main() -> None:
    queue = json.loads((ROOT / "queue-entries.partial.json").read_text())
    plan = json.loads((ROOT / "case-plan.json").read_text())
    cases = {row["case_id"] for row in plan["cases"]}
    rows = queue["cases"]
    if len(rows) != len(cases) or {row["case_id"] for row in rows} != cases:
        raise ValueError("queue does not cover all exact taxi cases once")
    comparisons = {row["comparison_id"] for row in queue["comparison_audit_commands"]}
    planned = {row["comparison_id"] for row in plan["comparisons"]}
    if len(queue["comparison_audit_commands"]) != len(planned) or comparisons != planned:
        raise ValueError("queue does not cover all exact taxi comparisons once")
    for row in rows:
        validate_row(row)
        for key, option_name in (("owner_release_command", "--attempt"),
                                 ("owner_release_command", "--receipt"),
                                 ("postprocessing_command", "--case"),
                                 ("postprocessing_command", "--manifest"),
                                 ("postprocessing_command", "--attempt"),
                                 ("additional_source_audit_command", "--pixel-review"),
                                 ("additional_source_audit_command", "--case"),
                                 ("additional_source_audit_command", "--job-id"),
                                 ("additional_source_audit_command", "--attempt-number"),
                                 ("additional_source_audit_command", "--recording-id"),
                                 ("additional_source_audit_command", "--physical-receipt"),
                                 ("additional_source_audit_command", "--output"),
                                 ("execute_command", "--assignment"),
                                 ("execute_command", "--job"),
                                 ("accept_command", "--batch"),
                                 ("accept_command", "--attempt"),
                                 ("accept_command", "--audit")):
            changed = dict(row)
            tokens = shlex.split(row[key])
            tokens[tokens.index(option_name) + 1] = "WRONG"
            changed[key] = shlex.join(tokens)
            try:
                validate_row(changed)
            except ValueError:
                pass
            else:
                raise AssertionError("broken stage command was accepted: " + key)
        changed = dict(row)
        changed["postprocessing_command"] += " --case WRONG"
        try:
            validate_row(changed)
        except ValueError:
            pass
        else:
            raise AssertionError("duplicate saved case selector was accepted")
        case = row["case_id"]
        events = [{"stage": stage, "case_id": case, "attempt_id": "diagnostic-attempt",
                   "job_id": "diagnostic-job", "passed": True} for stage in REQUIRED]
        replay(events, case)
        for broken in (
            events[:-1],
            [*events[:3], events[4], events[3], events[5]],
            [*events[:4], {**events[4], "passed": False}, events[5]],
            [*events[:4], {**events[4], "attempt_id": "different"}, events[5]],
        ):
            try:
                replay(broken, case)
            except ValueError:
                pass
            else:
                raise AssertionError("invalid handoff was accepted")
    print(f"assignment-local diagnostic handoff: {len(rows)} exact cases and {len(comparisons)} comparisons passed; command, missing, reordered, rejected and cross-attempt negatives rejected")


if __name__ == "__main__":
    main()
