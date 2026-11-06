"""Audit the source identity and limits of this unselected statutory review."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
ASSIGNMENT_ID = HERE.name
source = json.loads((ROOT / "inputs" / ASSIGNMENT_ID / "assignment.json").read_text())
witnesses = json.loads((ROOT / "inputs" / ASSIGNMENT_ID / "witnesses.json").read_text())
topics = json.loads((ROOT / "inputs/coverage/branch-sources.json").read_text())
review = json.loads((HERE / "statutory-review.json").read_text())
result = json.loads((HERE / "result.json").read_text())
assert review["assignment_id"] == source["assignment_id"] == ASSIGNMENT_ID
assert review["frozen_cell"] == {
    key: source["cell"][key] for key in ("layout", "maneuver", "control")
} | {"actor": source["actor"]}
law = topics["laws"][source["law_id"]] if "laws" in topics else topics[source["law_id"]]
assert law["law"]["text"] == source["law_record"]["text"]
assert {topic for branch in review["branches"] for topic in branch["source_topics"]} == set(law["topics"])
assert len(review["branches"]) == 4
assert all(branch["status"] == "unproven" for branch in review["branches"])
assert len(witnesses) == 1 and witnesses[0]["provenance_status"] == "membership_only_current_requirement_unreviewed"
assert len(witnesses[0]["witness"]["recording_ids"]) == 3
assert result["status"] == "blocked" and result["cases_selected"] == 0
assert review["cpu_readiness"] is False and review["physical_observation_claimed"] is False
print("C110454 statutory branch review: source identity and blocked scope passed; four branches remain unproven")
