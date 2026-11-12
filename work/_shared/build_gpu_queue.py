"""Assemble the canonical delivery queue from proven assignment packages.

This tool never executes a queued command. It refuses incomplete packages and
leaves the existing canonical queue untouched on any failed source join.
"""

import argparse
from hashlib import sha256
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
LOCAL = "python scenario_pipeline/pipeline.py"


def read(path):
    return json.loads(path.read_text())


def digest(path):
    return sha256(path.read_bytes()).hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def local_command(action, assignment, case, candidate=None):
    command = (f"{LOCAL} {action} --repo \"$REPO\" --batch \"$BATCH\" "
               f"--db \"$DB\" --assignment {assignment} --case {case}")
    if action == "prepare-delivery":
        return command + (f" --candidate {candidate}" if candidate else "")
    command += ' --run "$RUN" --job "$JOB_ID"'
    if action == "execute-delivery":
        return command + (' --python "$CARLA_PYTHON" --host "$CARLA_HOST" '
                          '--port "$CARLA_PORT"')
    return command + ' --attempt "$ATTEMPT_ID" --audit "$AUDIT_RECEIPT"'


def build(repo=ROOT, assignment_ids=None, require_ready=True):
    repo = Path(repo)
    batch = read(repo / "batch.json")
    coverage_path = repo / "work/_shared/branch-coverage.json"
    additional = ([row["assignment_id"] for row in
                   read(coverage_path).get("additional_bindings", [])]
                  if coverage_path.is_file() else [])
    assigned = list(batch["assignments"]) + additional
    selected = assigned if assignment_ids is None else list(assignment_ids)
    require(len(selected) == len(set(selected)), "Duplicate assignment in queue selection")
    require(set(selected) <= set(assigned), "Queue selects an unassigned package")
    rows, comparisons = [], []
    for assignment in selected:
        folder = repo / "work" / assignment
        result_path = folder / "result.json"
        require(result_path.is_file(), f"Missing result: {assignment}")
        result = read(result_path)
        if require_ready:
            require(result.get("status") == "ready" and
                    result.get("readiness_kind") == "delivery_prepared",
                    f"Package is not delivery ready: {assignment}")
        manifest_path = folder / "execution-manifest.json"
        plan_path = folder / "case-plan.json"
        source_queue_path = folder / "gpu-queue.json"
        require(all(path.is_file() for path in
                    (manifest_path, plan_path, source_queue_path)),
                f"Missing exact package queue sources: {assignment}")
        manifest, plan, source = map(read, (manifest_path, plan_path, source_queue_path))
        require(manifest.get("assignment_id") == assignment and
                plan.get("assignment_id") == assignment and
                source.get("assignment_id") == assignment and
                source.get("execution_manifest_sha256") == digest(manifest_path) and
                source.get("case_plan_sha256") == digest(plan_path),
                f"Stale or crossed package queue: {assignment}")
        cases = {entry["case_id"]: entry for entry in manifest["cases"]}
        planned = [entry["case_id"] for entry in plan["cases"]]
        queued = {entry["case_id"]: entry for entry in source["cases"]}
        require(len(cases) == len(manifest["cases"]) and
                len(queued) == len(source["cases"]) and
                len(planned) == len(set(planned)) and
                set(cases) == set(planned) == set(queued),
                f"Exact case coverage differs: {assignment}")
        for case in planned:
            entry, source_row = cases[case], queued[case]
            require(digest(folder / entry["construction"]) ==
                    entry["construction_sha256"] == source_row["construction_sha256"],
                    f"Stale construction: {case}")
            candidates = {item["id"]: item for item in entry.get("candidates", [])}
            require(set(source_row.get("candidate_commands", {})) == set(candidates),
                    f"Fallback queue mismatch: {case}")
            for item in candidates.values():
                require(digest(folder / item["construction"]) ==
                        item["construction_sha256"], f"Stale fallback: {case}")
            acceptance = entry.get("delivery_acceptance", {})
            require(acceptance.get("case_id") == case and
                    acceptance.get("test_exit_code") == 0 and
                    digest(folder / acceptance["script"]) == acceptance["script_sha256"] and
                    digest(folder / acceptance["test_log"]) == acceptance["test_log_sha256"],
                    f"Missing or stale independent delivery audit: {case}")
            require(case in source_row.get("capture_command", "") and
                    case in source_row.get("postprocessing_command", "") and
                    case in acceptance["command"] and
                    case in source_row.get("additional_source_audit_command", "") and
                    '"$ATTEMPT"' in source_row["additional_source_audit_command"],
                    f"Wrong exact command binding: {case}")
            release_receipt = f'"$ATTEMPT/owner-released-{case}.json"'
            rows.append({
                "order": len(rows) + 1, "assignment_id": assignment, "case_id": case,
                "capture_command": source_row["capture_command"],
                "postprocessing_command": (source_row["postprocessing_command"] +
                                           f" --owner-release-receipt {release_receipt}"),
                "owner_release_command": (
                    '.venv-cpu/bin/python runtime.py owner-released '
                    f'--attempt "$ATTEMPT" --receipt {release_receipt} '
                    '--acknowledge-owner-released'),
                "additional_source_audit_command": source_row[
                    "additional_source_audit_command"],
                "prepare_command": local_command("prepare-delivery", assignment, case),
                "execute_command": local_command("execute-delivery", assignment, case),
                "accept_command": local_command("accept-delivery", assignment, case),
                "candidate_commands": {candidate: local_command(
                    "prepare-delivery", assignment, case, candidate)
                    for candidate in candidates},
            })
        expected = {item["comparison_id"]: item for item in plan["comparisons"]}
        queued_comparisons = {item["comparison_id"]: item for item in source["comparisons"]}
        require(len(expected) == len(plan["comparisons"]) and
                len(queued_comparisons) == len(source["comparisons"]) and
                set(expected) == set(queued_comparisons),
                f"Comparison queue differs: {assignment}")
        for comparison in plan["comparisons"]:
            name = comparison["comparison_id"]
            require(queued_comparisons[name]["case_ids"] == comparison["case_ids"],
                    f"Comparison members differ: {assignment}/{name}")
            command = queued_comparisons[name].get("audit_command")
            require(isinstance(command, str) and name in command and
                    assignment in command,
                    f"Missing exact executable comparison audit command: {assignment}/{name}")
            comparisons.append({"assignment_id": assignment, "comparison_id": name,
                                "command": command})
    return {"format": "worker-ordered-gpu-queue", "batch_id": batch["batch_id"],
            "cases": rows, "comparison_audit_commands": comparisons,
            "physical_or_legal_acceptance_claimed": False}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--preview", nargs="*", metavar="ASSIGNMENT")
    args = parser.parse_args()
    preview = args.preview is not None
    output = ROOT / "work/_shared" / ("gpu-queue-preview.json" if preview else "gpu-queue.json")
    queue = build(assignment_ids=args.preview if preview else None,
                  require_ready=not preview)
    output.write_text(json.dumps(queue, indent=2) + "\n")
    print(json.dumps({"cases": len(queue["cases"]),
                      "comparisons": len(queue["comparison_audit_commands"]),
                      "path": str(output), "sha256": digest(output)}))
