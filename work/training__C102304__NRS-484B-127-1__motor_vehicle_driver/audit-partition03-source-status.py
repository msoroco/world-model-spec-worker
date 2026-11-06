"""Read-only exact-source and honest-status audit for the owned partition."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PARTITION = ROOT / "partitions/full-train-03.json"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    partition = json.loads(PARTITION.read_text())
    records = []
    for assignment_id in partition["assignment_ids"]:
        source_path = ROOT / "inputs" / assignment_id / "assignment.json"
        work_dir = ROOT / "work" / assignment_id
        plan_path = work_dir / "case-plan.json"
        result_path = work_dir / "result.json"
        source = json.loads(source_path.read_text())
        plan = json.loads(plan_path.read_text())
        result = json.loads(result_path.read_text())
        assert source["assignment_id"] == assignment_id
        assert plan["assignment_id"] == assignment_id
        assert result["assignment_id"] == assignment_id
        assert plan["source_law"]["text"] == source["law_record"]["text"]
        assert plan["source_law"]["source"] == source["law_record"]["source"]
        assert result["input_sha256"] == sha(source_path)
        assert result["status"] == "blocked"
        assert result["readiness_kind"] == "none"
        assert result["counts"]["delivery_cases_prepared"] == 0
        topics = {topic["topic_id"] for topic in plan["source_topic_inventory"]}
        dispositions = {item["requirement"]: item for item in plan["requirement_dispositions"]}
        assert topics == set(dispositions)
        case_ids = {case["case_id"] for case in plan["cases"]}
        assert all(case["planning_status"] == "unverified" for case in plan["cases"])
        assert all(comparison["status"] == "planned_only" for comparison in plan["comparisons"])
        for item in dispositions.values():
            if item["status"] == "selected_required":
                assert set(item["case_ids"]) == case_ids
            else:
                assert item["status"] in ("alternative_pending", "exception_pending")
                assert not item["case_ids"]
        records.append({
            "assignment_id": assignment_id,
            "input_sha256": sha(source_path),
            "case_plan_sha256": sha(plan_path),
            "result_sha256": sha(result_path),
            "statutory_topic_count": sum(x.startswith("text-") for x in topics),
            "selected_required": sorted(x for x, d in dispositions.items() if d["status"] == "selected_required"),
            "alternative_pending": sorted(x for x, d in dispositions.items() if d["status"] == "alternative_pending"),
            "exception_pending": sorted(x for x, d in dispositions.items() if d["status"] == "exception_pending"),
            "selected_delivery_cases": 0,
            "status": "blocked",
        })
    print(json.dumps({"format": "partition03-source-status-audit-v1",
                      "partition_sha256": sha(PARTITION),
                      "assignment_count": len(records),
                      "selected_delivery_cases": 0,
                      "records": records}, indent=2))


if __name__ == "__main__":
    main()
