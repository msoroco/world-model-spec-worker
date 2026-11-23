"""Check exact declarative dispatch shape without starting local/GPU work."""
from __future__ import annotations

import json
from pathlib import Path
import shlex

ROOT = Path(__file__).resolve().parent
ASSIGNMENT = ROOT.name


def option(tokens: list[str], name: str) -> str | None:
    return tokens[tokens.index(name) + 1] if name in tokens and tokens.index(name) + 1 < len(tokens) else None


def check(rows: list[dict], expected: set[str]) -> None:
    cases = [item["case_id"] for item in rows]
    if len(cases) != len(expected) or set(cases) != expected:
        raise ValueError("exact dispatch coverage differs")
    for row in rows:
        case = row["case_id"]
        for key, verb in (("prepare_command", "prepare-delivery"),
                          ("execute_command", "execute-delivery"),
                          ("accept_command", "accept-delivery")):
            tokens = shlex.split(row[key])
            if (verb not in tokens or option(tokens, "--case") != case or
                    option(tokens, "--assignment") != ASSIGNMENT or
                    option(tokens, "--batch") != "full-test-delivery"):
                raise ValueError("canonical local command differs: " + key)
        execute = shlex.split(row["execute_command"])
        if any(option(execute, key) != value for key, value in (
                ("--python", "$CARLA_PYTHON"), ("--host", "$CARLA_HOST"),
                ("--port", "$CARLA_PORT"), ("--job", "$JOB_ID"))):
            raise ValueError("exact Native execution parameters differ")
        if option(shlex.split(row["accept_command"]), "--review-archive") != "/external/archive":
            raise ValueError("external review archive differs")
        if option(shlex.split(row["postprocessing_command"]), "--case") != case:
            raise ValueError("saved processing selects another case")
        source = shlex.split(row["additional_source_audit_command"])
        if option(source, "--case-id") != case or option(source, "--pixel-review") is None:
            raise ValueError("source audit omits exact case or actual pixels")
        if case not in shlex.split(row["owner_release_command"])[0]:
            raise ValueError("owner release loses case context")


def main() -> None:
    queue = json.loads((ROOT / "queue-entries.partial.json").read_text())
    plan = json.loads((ROOT / "case-plan.json").read_text())
    expected = {row["case_id"] for row in plan["cases"]}
    check(queue["cases"], expected)
    comparisons = {row["comparison_id"] for row in queue["comparison_audit_commands"]}
    if comparisons != {row["comparison_id"] for row in plan["comparisons"]}:
        raise ValueError("comparison audit queue coverage differs")
    changed = [dict(row) for row in queue["cases"]]
    changed[0]["case_id"] = changed[1]["case_id"]
    try:
        check(changed, expected)
    except ValueError as error:
        if str(error) != "exact dispatch coverage differs":
            raise
    else:
        raise AssertionError("duplicate dispatch accepted")
    changed = [dict(row) for row in queue["cases"]]
    changed[0]["accept_command"] = changed[0]["accept_command"].replace("/external/archive", "$LOCAL_ROOT")
    try:
        check(changed, expected)
    except ValueError as error:
        if str(error) != "external review archive differs":
            raise
    else:
        raise AssertionError("non-external archive accepted")
    print(f"{ASSIGNMENT}: exact 3-case dispatch and 2-comparison coverage passed; duplicate and archive negatives rejected")


if __name__ == "__main__":
    main()
