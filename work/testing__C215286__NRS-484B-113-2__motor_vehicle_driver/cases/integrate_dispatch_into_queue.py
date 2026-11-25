"""Idempotently place this assignment's exact dispatch rows in the shared queue."""
import json
from pathlib import Path

PACKAGE = Path(__file__).resolve().parents[1]
REPO = PACKAGE.parents[1]
QUEUE = REPO / "work/_shared/gpu-queue.json"


def write(path, value):
    path.write_text(json.dumps(value, indent=2) + "\n")


def integrate():
    plan = json.loads((PACKAGE / "dispatch-plan.json").read_text())
    aid = PACKAGE.name
    if plan.get("format") != "worker-assignment-dispatch-plan" or plan.get("assignment_id") != aid:
        raise ValueError("Exact package dispatch plan required")
    if QUEUE.is_file():
        queue = json.loads(QUEUE.read_text())
        if queue.get("format") != "worker-ordered-gpu-queue":
            raise ValueError("Existing queue format differs")
    else:
        queue = {"format": "worker-ordered-gpu-queue", "status": "partial",
                 "cases": [], "comparison_audit_commands": []}
    others = [row for row in queue["cases"] if row.get("assignment_id") != aid]
    existing = [row for row in queue["cases"] if row.get("assignment_id") == aid]
    if existing and {row["case_id"] for row in existing} != {row["case_id"] for row in plan["cases"]}:
        raise ValueError("Partial existing assignment queue differs")
    rows = others + plan["cases"]
    if len({(row["assignment_id"], row["case_id"]) for row in rows}) != len(rows):
        raise ValueError("Duplicate exact delivery case")
    for order, row in enumerate(rows, 1):
        row["order"] = order
    comparisons = [row for row in queue["comparison_audit_commands"]
                   if row.get("assignment_id") != aid] + plan["comparison_audit_commands"]
    if len({(row["assignment_id"], row["comparison_id"]) for row in comparisons}) != len(comparisons):
        raise ValueError("Duplicate exact comparison")
    queue.update(cases=rows, comparison_audit_commands=comparisons,
                 status="partial", scope="Incremental exact command inventory; full batch and local integration proof pending")
    write(QUEUE, queue)
    return {"cases": len(rows), "comparisons": len(comparisons),
            "c215286_cases": len(plan["cases"]),
            "c215286_comparisons": len(plan["comparison_audit_commands"])}


if __name__ == "__main__":
    print(json.dumps(integrate(), sort_keys=True))
