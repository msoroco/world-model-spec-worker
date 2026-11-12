"""Build the linked cell's exact Native and saved-processing queue."""

from hashlib import sha256
import json
from pathlib import Path
import shlex

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
PROOFS = {
    "opposing_left_turn": "turn-saved-proof.json",
    "opposing_left_intent_hold": "intent-saved-proof.json",
    "opposing_left_shallow_turn": "shallow-saved-proof.json",
    **{f"turn_release_delay-{i:04d}": f"turn_release_delay-{i:04d}-saved-proof.json"
       for i in range(3)},
}


def digest(path):
    return sha256(Path(path).read_bytes()).hexdigest()


def local_audit_command(acceptance, case_id):
    tokens = shlex.split(acceptance["command"])
    if tokens[0].endswith("/.venv-cpu/bin/python"):
        tokens[0] = ".venv-cpu/bin/python"
    if tokens[1].startswith(str(ROOT / "work")):
        tokens[1] = str(Path(tokens[1]).relative_to(ROOT))
    if "--case" not in tokens or tokens[tokens.index("--case") + 1] != case_id:
        raise ValueError("Delivery audit selects another exact case: " + case_id)
    for option, value in (("--attempt", '"$ATTEMPT"'),
                          ("--report", '"$ANALYSIS_REPORT"')):
        if option not in tokens:
            raise ValueError("Delivery audit lacks retained source: " + case_id)
        tokens[tokens.index(option) + 1] = value
    return " ".join(token if token.startswith('"$') else shlex.quote(token)
                    for token in tokens)


def build(manifest_path=HERE / "execution-manifest.json",
          plan_path=HERE / "case-plan.json"):
    manifest_path, plan_path = Path(manifest_path), Path(plan_path)
    manifest, plan = json.loads(manifest_path.read_text()), json.loads(plan_path.read_text())
    assignment = manifest["assignment_id"]
    if assignment != plan["assignment_id"] or manifest.get("format") != "worker-execution-manifest":
        raise ValueError("Queue manifest and plan identities differ")
    selected = [case["case_id"] for case in plan["cases"]]
    entries = {entry["case_id"]: entry for entry in manifest["cases"]}
    if len(selected) != len(set(selected)) or len(entries) != len(manifest["cases"]) or set(selected) != set(entries):
        raise ValueError("Queue must cover every selected case once")
    manifest_hash = digest(manifest_path)
    rows = []
    for case_id in selected:
        entry = entries[case_id]
        if digest(HERE / entry["construction"]) != entry["construction_sha256"]:
            raise ValueError("Stale exact construction: " + case_id)
        short = case_id[len(assignment) + 2:]
        if short not in PROOFS:
            raise ValueError("No saved proof binding: " + case_id)
        proof_path = HERE / PROOFS[short]
        proof = json.loads(proof_path.read_text())
        if (proof["case_id"] != case_id or proof["manifest_sha256"] != manifest_hash or
                proof["construction_sha256"] != entry["construction_sha256"] or
                proof["exit_code"] != 0 or proof["originals_preserved"] is not True or
                proof["missing_evidence"] is not False or
                digest(HERE / proof["log"]) != proof["log_sha256"]):
            raise ValueError("Stale or failed saved proof: " + case_id)
        candidates = {}
        for candidate in entry.get("candidates", []):
            if digest(HERE / candidate["construction"]) != candidate["construction_sha256"]:
                raise ValueError("Stale fallback construction: " + case_id)
            candidates[candidate["id"]] = (
                f'.venv-cpu/bin/python runtime.py capture --manifest {manifest_path.relative_to(ROOT)} '
                f'--case {case_id} --candidate {candidate["id"]} --output "$ATTEMPT" '
                '--host "$CARLA_HOST" --port "$CARLA_PORT" --python "$CARLA_PYTHON"')
        post = entry["post_capture"]
        if post.get("recorded_only") is not True or case_id not in post.get("command", ""):
            raise ValueError("Missing exact saved-only command: " + case_id)
        rows.append({
            "order": len(rows) + 1, "assignment_id": assignment, "case_id": case_id,
            "construction_sha256": entry["construction_sha256"],
            "saved_proof": proof_path.name, "saved_proof_sha256": digest(proof_path),
            "capture_command": (
                f'.venv-cpu/bin/python runtime.py capture --manifest {manifest_path.relative_to(ROOT)} '
                f'--case {case_id} --output "$ATTEMPT" --host "$CARLA_HOST" '
                '--port "$CARLA_PORT" --python "$CARLA_PYTHON"'),
            "candidate_commands": candidates,
            "postprocessing_command": post["command"],
            "additional_source_audit_command": local_audit_command(entry["delivery_acceptance"], case_id),
            "candidate_selection_rule": "Use only the declared physical trigger.",
        })
    proof_path = HERE / "comparison-dispatch-proof.json"
    proof = json.loads(proof_path.read_text())
    if (proof["manifest_sha256"] != manifest_hash or
            proof["case_plan_sha256"] != digest(plan_path) or
            proof["dispatcher_sha256"] != digest(HERE / "comparison_dispatch.py") or
            proof["negative_exit_code"] == 0):
        raise ValueError("Linked comparison proof is stale")
    proven = {row["comparison_id"]: row for row in proof["comparisons"]}
    if len(proven) != len(proof["comparisons"]):
        raise ValueError("Repeated comparison proof")
    comparisons = []
    for item in plan["comparisons"]:
        name, cases = item["comparison_id"], item["case_ids"]
        row = proven.get(name)
        if (not row or row["case_ids"] != cases or row["exit_code"] != 0 or
                row["saved_proof_sha256"] != [digest(HERE / PROOFS[case[len(assignment) + 2:]])
                                                for case in cases]):
            raise ValueError("Comparison lacks current exact source proof: " + name)
        command = (f'.venv-cpu/bin/python {Path("work") / assignment / "comparison_dispatch.py"} '
                   f'--comparison {name} ' +
                   " ".join(f'--attempt "$ATTEMPT_{i}"' for i in range(1, len(cases) + 1)) +
                   ' --output "$COMPARISON_REPORT"')
        comparisons.append({"comparison_id": name, "case_ids": cases,
                            "audit_script_sha256": digest(HERE / "comparison_dispatch.py"),
                            "audit_proof_sha256": digest(proof_path),
                            "audit_command": command})
    return {"format": "worker-assignment-ordered-gpu-queue",
            "assignment_id": assignment, "execution_manifest_sha256": manifest_hash,
            "case_plan_sha256": digest(plan_path), "cases": rows,
            "comparisons": comparisons, "physical_or_legal_acceptance_claimed": False}


if __name__ == "__main__":
    result = build()
    output = HERE / "gpu-queue.json"
    output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"cases": len(result["cases"]),
                      "comparisons": len(result["comparisons"]), "sha256": digest(output)}))
