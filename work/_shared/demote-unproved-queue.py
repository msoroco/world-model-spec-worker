"""Align historical queue labels with current assignment readiness markers."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
QUEUE = ROOT / "work/_shared/gpu-queue.json"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    queue = json.loads(QUEUE.read_text())
    batch = json.loads((ROOT / "batch.json").read_text())
    statuses = {aid: json.loads((ROOT / "work" / aid / "result.json").read_text())["status"]
                for aid in batch["assignments"]}
    before = sha(QUEUE)
    changed = []
    for section in ("cases", "comparison_audit_commands"):
        for row in queue.get(section, []):
            if statuses.get(row.get("assignment_id")) == "partial" and row.get("status") == "ready":
                if row.get("dispatchable") is not False:
                    raise ValueError("Historical ready row may have been dispatched")
                row["status"] = "partial"
                changed.append({"section": section,
                                "assignment_id": row["assignment_id"],
                                "id": row.get("case_id", row.get("comparison_id"))})
    QUEUE.write_text(json.dumps(queue, indent=2) + "\n")
    report = {"format": "worker-queue-readiness-reconciliation",
              "old_queue_sha256": before, "new_queue_sha256": sha(QUEUE),
              "demoted_rows": changed, "dispatchable_rows_changed": 0}
    target = ROOT / "work/_shared/queue-readiness-reconciliation-2026-11-18.json"
    target.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"demoted": len(changed), "queue_sha256": report["new_queue_sha256"]}))


if __name__ == "__main__":
    main()
