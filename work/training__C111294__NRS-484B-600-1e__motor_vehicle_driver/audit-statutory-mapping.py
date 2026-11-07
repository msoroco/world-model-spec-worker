"""Independent exact-source audit of the pending C111294 branch mapping."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
LAW = "NRS-484B-600-1e"
TOPICS = {"text-0", "text-1", "reviewed-scope-0", "reviewed-scope-1"}


def main() -> None:
    source_path = REPO / "inputs/coverage/branch-sources.json"
    source = json.loads(source_path.read_text())["laws"][LAW]
    plan = json.loads((ROOT / "case-plan.json").read_text())
    matrix_path = REPO / "work/_shared/branch-coverage.json"
    matrix = json.loads(matrix_path.read_text())
    law = matrix["laws"][LAW]
    assert set(source["topics"]) == TOPICS
    assert source["law"]["text"] == plan["source_law_text"]
    assert source["law"]["source"] == plan["source_law_citation"]
    assert source["law"]["text"].endswith("greater than 80 miles per hour.")
    assert len(law["branches"]) == 1
    branch = law["branches"][0]
    assert set(branch["topic_ids"]) == TOPICS
    assert branch["status"] == "pending_review"
    assert branch["assignment_id"] == plan["assignment_id"]
    assert set(branch["case_ids"]) == {c["case_id"] for c in plan["cases"]}
    assert branch["comparison_ids"] == [plan["comparisons"][0]["comparison_id"]]
    assert plan["comparisons"][0]["deliberate_differences"] == ["observed_speed"]
    assert sorted(c["requested_setting"] for c in plan["cases"]) == [75, 79.5, 85]
    assert {d["requirement"] for d in plan["requirement_dispositions"]} == TOPICS
    print(json.dumps({"passed": True, "law_id": LAW,
                      "source_sha256": hashlib.sha256(source_path.read_bytes()).hexdigest(),
                      "matrix_sha256": hashlib.sha256(matrix_path.read_bytes()).hexdigest(),
                      "topic_count": len(TOPICS), "case_count": len(plan["cases"]),
                      "branch_status": "pending_review", "selected": False}, sort_keys=True))


if __name__ == "__main__":
    main()
