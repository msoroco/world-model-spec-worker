"""Check selected dispatch inventory and every canonical command shape."""
import json
import shlex
from pathlib import Path

from build_dispatch_plan import build

HERE = Path(__file__).resolve().parents[1]


def check():
    generated = build()
    saved = json.loads((HERE / "dispatch-plan.json").read_text())
    if saved != generated:
        raise ValueError("Saved dispatch plan differs from selected manifest")
    manifest = json.loads((HERE / "execution-manifest.json").read_text())
    plan = json.loads((HERE / "case-plan.json").read_text())
    if len(saved["cases"]) != 6 or len(saved["comparison_audit_commands"]) != 3:
        raise ValueError("Six cases and three comparisons required")
    for row, entry in zip(saved["cases"], manifest["cases"]):
        if (row["case_id"] != entry["case_id"] or set(row["candidate_commands"]) !=
                {candidate["id"] for candidate in entry["candidates"]}):
            raise ValueError("Exact case or fallback inventory differs")
        for key in ("prepare_command", "execute_command", "accept_command",
                    "capture_command", "postprocessing_command", "owner_release_command",
                    "additional_source_audit_command"):
            shlex.split(row[key])
            if row["case_id"] not in row[key]:
                raise ValueError("Command omits exact case: " + key)
        for command in row["candidate_commands"].values():
            shlex.split(command)
    if {row["comparison_id"] for row in saved["comparison_audit_commands"]} != {
            row["comparison_id"] for row in plan["comparisons"]}:
        raise ValueError("Comparison inventory differs")
    for row in saved["comparison_audit_commands"]:
        shlex.split(row["command"])
    return {"cases": len(saved["cases"]),
            "candidates": sum(len(row["candidate_commands"]) for row in saved["cases"]),
            "comparisons": len(saved["comparison_audit_commands"])}


if __name__ == "__main__":
    print(json.dumps(check(), sort_keys=True))
