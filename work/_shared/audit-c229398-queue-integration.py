"""Check C229398 selected delivery source audits in the ordered intent queue."""

import copy
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
ASSIGNMENT = "training__C229398__LVMC-11-52-060__motor_vehicle_driver"
QUEUE = ROOT / "work" / "_shared" / "gpu-queue.json"
MANIFEST = ROOT / "work" / ASSIGNMENT / "execution-manifest.json"


def require(condition, message):
    if not condition:
        raise ValueError(message)


def check(rows, cases):
    selected = [row for row in rows if row["assignment_id"] == ASSIGNMENT]
    require(len(selected) == len(cases) == 3, "selected queue case count differs")
    require({row["case_id"] for row in selected} == set(cases), "selected queue IDs differ")
    for row in selected:
        command = cases[row["case_id"]]["delivery_acceptance"]["production_command"]
        require(row["status"] == "partial" and row["selected"] is True, "queue status differs")
        require(row["dispatchable"] is False, "unproved queue row is dispatchable")
        require(row["additional_source_audit_command"] == command, "source audit command differs")
        require("--candidate" in command and "--attempt" in command and "--saved" in command,
                "source audit command is incomplete")
    return selected


def run():
    queue = json.loads(QUEUE.read_text())
    manifest = json.loads(MANIFEST.read_text())
    cases = {case["case_id"]: case for case in manifest["cases"]}
    rows = queue["cases"]
    selected = check(rows, cases)

    changed = copy.deepcopy(rows)
    for row in changed:
        if row["case_id"] == selected[0]["case_id"]:
            row["additional_source_audit_command"] += " --fixture"
            break
    try:
        check(changed, cases)
    except ValueError:
        changed_command_rejected = True
    else:
        changed_command_rejected = False
    require(changed_command_rejected, "mutated source command passed")

    dispatched = copy.deepcopy(rows)
    for row in dispatched:
        if row["case_id"] == selected[0]["case_id"]:
            row["dispatchable"] = True
            break
    try:
        check(dispatched, cases)
    except ValueError:
        premature_dispatch_rejected = True
    else:
        premature_dispatch_rejected = False
    require(premature_dispatch_rejected, "premature dispatch passed")

    return {
        "passed": True,
        "assignment_id": ASSIGNMENT,
        "selected_cases": len(selected),
        "source_commands_bound": len(selected),
        "changed_command_rejected": changed_command_rejected,
        "premature_dispatch_rejected": premature_dispatch_rejected,
        "manifest_sha256": hashlib.sha256(MANIFEST.read_bytes()).hexdigest(),
        "queue_sha256": hashlib.sha256(QUEUE.read_bytes()).hexdigest(),
        "scope": "CPU intent and command binding only; no dispatch or original source acceptance",
    }


if __name__ == "__main__":
    print(json.dumps(run(), indent=2))
