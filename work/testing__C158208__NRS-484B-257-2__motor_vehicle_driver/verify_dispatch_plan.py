"""Check the returned exact-case local dispatch fragment without running it."""

import json
from pathlib import Path
import shlex

HERE = Path(__file__).resolve().parent


def main():
    dispatch = json.loads((HERE / "dispatch-plan.json").read_text())
    manifest = json.loads((HERE / "execution-manifest.json").read_text())
    plan = json.loads((HERE / "case-plan.json").read_text())
    expected = {entry["case_id"]: entry for entry in manifest["cases"]}
    rows = dispatch["cases"]
    if (dispatch.get("assignment_id") != HERE.name
            or len(rows) != len(expected)
            or [row["order"] for row in rows] != list(range(1, len(rows) + 1))
            or {row["case_id"] for row in rows} != set(expected)):
        raise ValueError("Exact selected dispatch coverage changed")
    for row in rows:
        case = row["case_id"]
        for field, verb in (("prepare_command", "prepare-delivery"),
                            ("execute_command", "execute-delivery"),
                            ("accept_command", "accept-delivery")):
            tokens = shlex.split(row[field])
            if case not in tokens or verb not in tokens:
                raise ValueError("Missing exact canonical command: " + field)
        if "--review-archive /external/archive" not in row["accept_command"]:
            raise ValueError("Acceptance review archive differs")
        for field in ("capture_command", "postprocessing_command",
                      "owner_release_command", "additional_source_audit_command"):
            if case not in row[field]:
                raise ValueError("Missing exact source command: " + field)
        candidates = row["candidate_commands"]
        if set(candidates) != {c["id"] for c in expected[case].get("candidates", [])}:
            raise ValueError("Fallback dispatch set differs")
        for candidate, command in candidates.items():
            if candidate not in shlex.split(command) or case not in shlex.split(command):
                raise ValueError("Fallback dispatch identity differs")
    comparisons = dispatch["comparison_audit_commands"]
    if {r["comparison_id"] for r in comparisons} != {
            r["comparison_id"] for r in plan["comparisons"]}:
        raise ValueError("Comparison dispatch coverage differs")
    print(json.dumps({"format": "c158208-dispatch-fragment-check", "cases": len(rows),
                      "comparisons": len(comparisons), "executed": False}, sort_keys=True))


if __name__ == "__main__":
    main()
