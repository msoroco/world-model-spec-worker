"""Check C10014's ordered dispatch intent without releasing any GPU job."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shlex

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
QUEUE = REPO / "work/_shared/gpu-queue.json"


def read(path: Path) -> dict:
    return json.loads(path.read_text())


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(ok: bool, message: str) -> None:
    if not ok:
        raise ValueError(message)


def contains_argument(command: str, flag: str, value: str) -> bool:
    tokens = shlex.split(command)
    return any(tokens[i:i + 2] == [flag, value] for i in range(len(tokens) - 1))


def audit(queue: dict, manifest: dict, plan: dict) -> dict:
    require(queue.get("format") in ("worker-ordered-gpu-queue", "worker-ordered-gpu-queue-v1"),
            "Unknown queue format")
    all_rows = queue.get("cases", [])
    require([row.get("order") for row in all_rows] == list(range(1, len(all_rows) + 1)),
            "Queue order is not consecutive")
    rows = [row for row in all_rows if row.get("assignment_id") == HERE.name]
    cases = {entry["case_id"]: entry for entry in manifest["cases"]}
    require(len(rows) == len(cases) and {row.get("case_id") for row in rows} == set(cases),
            "Selected cases do not match C10014 queue rows")
    for row in rows:
        case = row["case_id"]
        require(row.get("dispatchable") is False and row.get("status") != "ready",
                "Partial case was released for dispatch")
        for field, subcommand in (("capture_command", "capture"),
                                  ("postprocessing_command", "process-saved")):
            command = row.get(field, "")
            require(subcommand in shlex.split(command) and
                    contains_argument(command, "--case", case) and
                    contains_argument(command, "--manifest", "work/" + HERE.name +
                                      "/execution-manifest.json"),
                    "Capture or saved-processing command selects another case")
        for field, subcommand in (("prepare_command", "prepare-delivery"),
                                  ("execute_command", "execute-delivery"),
                                  ("accept_command", "accept-delivery")):
            command = row.get(field, "")
            require(subcommand in shlex.split(command) and
                    contains_argument(command, "--assignment", HERE.name) and
                    contains_argument(command, "--case", case),
                    "Canonical delivery command selects another case")
        require(case in row.get("owner_release_command", "") and
                case in row.get("additional_source_audit_command", ""),
                "Ownership or source audit command lacks case identity")
        fallbacks = {item["id"] for item in cases[case].get("candidates", [])}
        commands = row.get("candidate_commands", {})
        require(set(commands) == fallbacks and all(
            case in command and candidate in command and
            "prepare-delivery-candidate.py" in command
            for candidate, command in commands.items()),
            "Queue fallback commands differ from selected construction")
    comparisons = [row for row in queue.get("comparison_audit_commands", [])
                   if row.get("assignment_id") == HERE.name]
    planned = {item["comparison_id"] for item in plan["comparisons"]}
    require(len(comparisons) == len(planned) and
            {row.get("comparison_id") for row in comparisons} == planned and
            all(row.get("dispatchable") is False and row.get("status") != "ready" and
                row["comparison_id"] in row.get("command", "")
                for row in comparisons),
            "Comparison queue does not match the controlled plan")
    return {"format": "c10014-queue-intent-audit", "passed": True,
            "cases": sorted(cases), "comparisons": sorted(planned),
            "dispatchable": False,
            "canonical_format_ready": queue["format"] == "worker-ordered-gpu-queue",
            "queue_sha256": sha(QUEUE),
            "manifest_sha256": sha(HERE / "execution-manifest.json"),
            "plan_sha256": sha(HERE / "case-plan.json")}


if __name__ == "__main__":
    report = audit(read(QUEUE), read(HERE / "execution-manifest.json"),
                   read(HERE / "case-plan.json"))
    print(json.dumps(report, indent=2))
