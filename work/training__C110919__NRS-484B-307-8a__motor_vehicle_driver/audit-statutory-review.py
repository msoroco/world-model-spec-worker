"""Check exact frozen source and honest scope of the red-signal review."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
source = json.loads((ROOT / "inputs" / HERE.name / "assignment.json").read_text())
coverage = json.loads((ROOT / "inputs/coverage/branch-sources.json").read_text())
review = json.loads((HERE / "statutory-review.json").read_text())
result = json.loads((HERE / "result.json").read_text())
law = coverage.get("laws", coverage)[source["law_id"]]
assert review["assignment_id"] == source["assignment_id"] == HERE.name
assert law["law"]["text"] == source["law_record"]["text"]
assert review["frozen_cell"] == {
    key: source["cell"][key] for key in ("layout", "maneuver", "control")
} | {"actor": source["actor"]}
assert {topic for branch in review["branches"] for topic in branch["source_topics"]} == set(law["topics"])
assert len(review["branches"]) == 6
assert all(branch["status"] == "unproven" and branch["needed_evidence"] for branch in review["branches"])
assert result["status"] == "blocked" and result["cases_selected"] == 0
assert review["cpu_readiness"] is False and review["physical_observation_claimed"] is False
print("C110919 red-signal review: exact source and six unproven branch alternatives passed")
