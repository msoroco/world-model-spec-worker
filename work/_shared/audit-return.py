"""Independent read-only audit of the best-effort planning return."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    batch = read(ROOT / "batch.json")
    assignments = batch["assignments"]
    partitions = sorted((ROOT / "partitions").glob("full-train-*.json"))
    allocated = [aid for path in partitions for aid in read(path)["assignment_ids"]]
    errors = []
    if len(allocated) != len(set(allocated)) or set(allocated) != set(assignments):
        errors.append("Partition assignment coverage differs from batch")
    counts = {"assignments": len(assignments), "packages": 0, "blocked": 0,
              "partial": 0, "ready": 0, "planning_cases": 0,
              "selected_delivery_cases": 0, "comparisons": 0,
              "proven_candidates": 0, "proven_reuses": 0}
    by_partition = {}
    for path in partitions:
        partition = read(path)
        pc = {"assigned": len(partition["assignment_ids"]), "packages": 0,
              "blocked": 0, "partial": 0, "ready": 0,
              "planning_cases": 0, "comparisons": 0}
        for aid in partition["assignment_ids"]:
            folder = ROOT / "work" / aid
            required = [folder / name for name in ("result.json", "case-plan.json", "HANDOFF.md")]
            if not all(file.is_file() for file in required):
                errors.append(f"{aid}: missing package file")
                continue
            result, plan = read(required[0]), read(required[1])
            source = read(ROOT / "inputs" / aid / "assignment.json")
            if (result.get("assignment_id") != aid or
                    result.get("input_sha256") != assignments[aid]["input_sha256"] or
                    result.get("applied_update") != batch["update_version"]):
                errors.append(f"{aid}: result identity or version differs")
            if any(plan.get(key) != source[key] for key in ("law_id", "cell_id", "actor")):
                errors.append(f"{aid}: plan scope differs")
            for ref in plan.get("sources", []):
                source_path = ROOT / ref["path"]
                if not source_path.is_file() or sha(source_path) != ref["sha256"]:
                    errors.append(f"{aid}: stale source {ref['path']}")
            ids = {case.get("case_id") for case in plan.get("cases", [])}
            if None in ids or len(ids) != len(plan.get("cases", [])):
                errors.append(f"{aid}: duplicate or missing case ID")
            for comparison in plan.get("comparisons", []):
                if not set(comparison.get("case_ids", [])) <= ids:
                    errors.append(f"{aid}: comparison has missing case")
            status = result.get("status")
            if status not in ("blocked", "partial", "ready"):
                errors.append(f"{aid}: invalid status")
            else:
                counts[status] += 1
                pc[status] += 1
            counts["packages"] += 1
            pc["packages"] += 1
            counts["planning_cases"] += len(ids)
            pc["planning_cases"] += len(ids)
            counts["comparisons"] += len(plan.get("comparisons", []))
            pc["comparisons"] += len(plan.get("comparisons", []))
            manifest = folder / "execution-manifest.json"
            if manifest.exists():
                entry = read(manifest)
                counts["selected_delivery_cases"] += len(entry.get("cases", []))
                counts["proven_candidates"] += sum(len(c.get("candidates", [])) for c in entry.get("cases", []))
            counts["proven_reuses"] += len(result.get("proven_reuses", []))
        by_partition[partition["partition_id"]] = pc
    coverage = read(ROOT / "work/_shared/branch-coverage.json")
    sources = read(ROOT / "inputs/coverage/branch-sources.json")["laws"]
    if set(coverage.get("laws", {})) != set(sources):
        errors.append("Shared law inventory omits source law")
    for law, source in sources.items():
        topics = {topic for branch in coverage["laws"].get(law, {}).get("branches", [])
                  for topic in branch.get("topic_ids", [])}
        if topics != set(source["topics"]):
            errors.append(f"{law}: source topic inventory differs")
    print(json.dumps({"passed": not errors, "counts": counts,
                      "partitions": by_partition, "laws": len(sources),
                      "source_topics": sum(len(v["topics"]) for v in sources.values()),
                      "errors": errors}, indent=2))
    raise SystemExit(0 if not errors else 1)


if __name__ == "__main__":
    main()
