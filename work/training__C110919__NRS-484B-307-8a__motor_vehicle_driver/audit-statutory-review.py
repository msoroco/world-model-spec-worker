"""Check exact frozen source and honest scope of the red-signal review."""
import json
import hashlib
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
assert all(branch.get('cpu_draft_evidence') and branch.get('remaining_exact_evidence')
           for branch in review['branches'])
for ref in review['source_refs']:
    assert (ROOT/ref).is_file()
assert hashlib.sha256((ROOT/'inputs/training__C110919__NRS-484B-307-8c__motor_vehicle_driver/assignment.json').read_bytes()).hexdigest() in review['external_cross_reference']
assert hashlib.sha256((ROOT/'inputs/training__C110919__NRS-484B-307-8d__motorcycle_or_moped_operator/assignment.json').read_bytes()).hexdigest() in review['external_cross_reference']
assert hashlib.sha256((HERE/'draft-execution-manifest.json').read_bytes()).hexdigest()==review['cpu_diagnostic_manifest_sha256']
assert hashlib.sha256((HERE/'package-probes-summary.json').read_bytes()).hexdigest()==review['cpu_package_probes_summary_sha256']
assert hashlib.sha256((HERE/'native/synthetic-comparison-audit.log').read_bytes()).hexdigest()==review['cpu_controlled_comparison_audit_sha256']
assert result["status"] == "blocked" and result["cases_selected"] == 0
assert review["cpu_readiness"] is False and review["physical_observation_claimed"] is False
print("C110919 red-signal review: exact source, CPU draft mapping and six unproven physical branch alternatives passed")
