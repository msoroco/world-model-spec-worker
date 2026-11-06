"""Read-only source and readiness inventory for this assignment's partition."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PARTITION = json.loads((ROOT / "partitions/full-train-01.json").read_text())
SOURCES = json.loads((ROOT / "inputs/coverage/branch-sources.json").read_text())
LAWS = SOURCES.get("laws", SOURCES)
rows = []
for assignment_id in PARTITION["assignment_ids"]:
    source_path = ROOT / "inputs" / assignment_id / "assignment.json"
    work_dir = ROOT / "work" / assignment_id
    source = json.loads(source_path.read_text())
    plan = json.loads((work_dir / "case-plan.json").read_text())
    result = json.loads((work_dir / "result.json").read_text())
    law = LAWS[source["law_id"]]
    assert source["assignment_id"] == plan["assignment_id"] == result["assignment_id"] == assignment_id
    assert result["input_sha256"] == hashlib.sha256(source_path.read_bytes()).hexdigest()
    assert plan["source_law_text"] == law["law"]["text"] == source["law_record"]["text"]
    assert (plan["law_id"], plan["cell_id"], plan["actor"]) == (
        source["law_id"], source["cell_id"], source["actor"])
    assert result["status"] == "blocked" and result["readiness_kind"] is None
    assert result["cases_selected"] == result["candidate_plans_proven"] == result["comparison_audits_passed"] == 0
    assert result["carla_executed"] is False and result["recordings_accepted"] == 0
    assert set(plan["cases"][0]["source_topic_ids"]) <= set(law["topics"])
    rows.append({"assignment_id": assignment_id,
                 "law_sha256": hashlib.sha256(source["law_record"]["text"].encode()).hexdigest(),
                 "topic_count": len(law["topics"]),
                 "case_drafts": len(plan["cases"]),
                 "status": result["status"],
                 "selected": result["cases_selected"]})
output = {"format": "worker-partition-source-status-audit-v1",
          "partition": PARTITION["partition_id"],
          "scope_sha256": PARTITION["scope_sha256"],
          "assignment_count": len(rows),
          "source_topic_count": sum(row["topic_count"] for row in rows),
          "case_draft_count": sum(row["case_drafts"] for row in rows),
          "blocked_count": sum(row["status"] == "blocked" for row in rows),
          "selected_count": sum(row["selected"] for row in rows),
          "rows": rows}
assert output["assignment_count"] == output["blocked_count"] == 32
assert output["selected_count"] == 0
target = Path(__file__).with_name("partition01-source-status-audit.json")
target.write_text(json.dumps(output, indent=2) + "\n")
print(json.dumps({key: output[key] for key in (
    "partition", "assignment_count", "source_topic_count", "case_draft_count",
    "blocked_count", "selected_count")}, sort_keys=True))
