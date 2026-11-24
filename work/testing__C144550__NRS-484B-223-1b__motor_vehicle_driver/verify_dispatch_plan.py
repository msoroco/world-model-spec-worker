"""Check this assignment's exact queue fragment before global integration."""

import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
dispatch = json.loads((HERE / "dispatch-plan.json").read_text())
manifest = json.loads((HERE / "execution-manifest.json").read_text())
plan = json.loads((HERE / "case-plan.json").read_text())
assert dispatch["status"] == "cpu_prepared_partial"
assert [row["case_id"] for row in dispatch["cases"]] == [entry["case_id"] for entry in manifest["cases"]]
assert [row["order"] for row in dispatch["cases"]] == list(range(1, len(dispatch["cases"]) + 1))
for row, entry in zip(dispatch["cases"], manifest["cases"]):
    for key in ("capture_command", "postprocessing_command", "owner_release_command",
                "additional_source_audit_command", "independent_delivery_audit_command",
                "prepare_command", "execute_command", "accept_command"):
        assert row["case_id"] in row[key], (row["case_id"], key)
    assert set(row["candidate_commands"]) == {item["id"] for item in entry["candidates"]}
    for name, command in row["candidate_commands"].items():
        assert name in command and row["case_id"] in command and "prepare-delivery" in command
assert [row["comparison_id"] for row in dispatch["comparison_audit_commands"]] == [
    item["comparison_id"] for item in plan["comparisons"]]
print("PASS", len(dispatch["cases"]), "ordered exact cases and",
      len(dispatch["comparison_audit_commands"]), "comparison audits")
