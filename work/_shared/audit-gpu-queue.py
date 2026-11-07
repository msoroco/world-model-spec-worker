"""Independent current-plan audit of the blocked ordered GPU intent queue."""
import argparse
import copy
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
QUEUE = HERE / "gpu-queue.json"
def expected_identities():
    batch = json.loads((ROOT / "batch.json").read_text())
    expected_cases = set()
    expected_comparisons = set()
    for aid in batch["assignments"]:
        result = json.loads((ROOT / "work" / aid / "result.json").read_text())
        if result.get("status") != "blocked" or result.get("selected_case_count", 0) != 0:
            raise ValueError("Blocked queue hides a selected or ready case")
        plan = json.loads((ROOT / "work" / aid / "case-plan.json").read_text())
        expected_cases.update((aid, case["case_id"]) for case in plan["cases"])
        expected_comparisons.update((aid, item["comparison_id"]) for item in plan["comparisons"])
    return expected_cases, expected_comparisons


def check(queue, expected_cases, expected_comparisons):
    rows = queue["cases"]
    comparisons = queue["comparison_audit_commands"]
    if ([row["order"] for row in rows] != list(range(1, len(rows) + 1))
            or len({(r["assignment_id"], r["case_id"]) for r in rows}) != len(rows)
            or {(r["assignment_id"], r["case_id"]) for r in rows} != expected_cases
            or len({(r["assignment_id"], r["comparison_id"]) for r in comparisons}) != len(comparisons)
            or {(r["assignment_id"], r["comparison_id"]) for r in comparisons} != expected_comparisons
            or any(r["dispatchable"] or r["status"] != "blocked" for r in rows)
            or any(r["dispatchable"] or r["status"] != "blocked" for r in comparisons)):
        raise ValueError("Queue order, uniqueness or blocked state invalid")
    for row in rows:
        case = row["case_id"]
        for key in ("capture_command", "postprocessing_command", "owner_release_command",
                    "additional_source_audit_command", "prepare_command",
                    "execute_command", "accept_command"):
            if case not in row[key]:
                raise ValueError("Case identity absent from queue command")
        if set(row["candidate_commands"]) != {"fallback1", "fallback2", "fallback3"}:
            raise ValueError("Fallback preparation missing")
        for candidate, command in row["candidate_commands"].items():
            if case not in command or candidate not in command:
                raise ValueError("Fallback identity absent")
    return len(rows), len(comparisons)


def run(case=None, comparison=None):
    queue = json.loads(QUEUE.read_text())
    expected_cases, expected_comparisons = expected_identities()
    cases, comparisons = check(queue, expected_cases, expected_comparisons)
    if case is not None and case not in {row["case_id"] for row in queue["cases"]}:
        raise ValueError("Case absent from queue")
    if comparison is not None and comparison not in {
            row["comparison_id"] for row in queue["comparison_audit_commands"]}:
        raise ValueError("Comparison absent from queue")
    missing = copy.deepcopy(queue)
    missing["cases"].pop()
    try:
        check(missing, expected_cases, expected_comparisons)
    except ValueError:
        pass
    else:
        raise AssertionError("Missing case passed queue audit")
    promoted = copy.deepcopy(queue)
    promoted["cases"][0]["dispatchable"] = True
    try:
        check(promoted, expected_cases, expected_comparisons)
    except ValueError:
        pass
    else:
        raise AssertionError("Unproved dispatch passed queue audit")
    return {
        "passed": True, "assignments": len(json.loads((ROOT / "batch.json").read_text())["assignments"]),
        "ordered_cases": cases, "comparison_rows": comparisons,
        "dispatchable_cases": 0, "missing_case_rejected": True,
        "unproved_dispatch_rejected": True,
        "queue_sha256": hashlib.sha256(QUEUE.read_bytes()).hexdigest(),
        "scope": "Blocked intent queue only; exact execution manifests, selected cases and physical acceptance absent",
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--case")
    parser.add_argument("--comparison")
    args = parser.parse_args()
    print(json.dumps(run(args.case, args.comparison), indent=2))
