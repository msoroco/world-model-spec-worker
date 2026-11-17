"""Generate the nine exact Native capture and saved-processing commands."""

from hashlib import sha256
import json
from pathlib import Path
import shlex


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def digest(path):
    return sha256(Path(path).read_bytes()).hexdigest()


def local_audit_command(acceptance, case_id):
    """Turn a proven diagnostic audit invocation into an exact local attempt command."""
    tokens = shlex.split(acceptance["command"])
    if tokens[0].endswith("/.venv-cpu/bin/python"):
        tokens[0] = ".venv-cpu/bin/python"
    if "--case" not in tokens or tokens[tokens.index("--case") + 1] != case_id:
        raise ValueError("Delivery auditor selects another case: " + case_id)
    replacements = {"--attempt": '"$ATTEMPT"',
                    "--output": '"$AUDIT_OUTPUT"',
                    "--positive": '"$BASELINE_ATTEMPT"',
                    "--baseline": '"$BASELINE_ATTEMPT"',
                    "--no-horn": '"$BASELINE_ATTEMPT"'}
    for option, value in replacements.items():
        if option in tokens:
            position = tokens.index(option) + 1
            if position >= len(tokens):
                raise ValueError("Audit option lacks value: " + option)
            tokens[position] = value
    if "--attempt" not in tokens or "--output" not in tokens:
        raise ValueError("Delivery audit needs an exact local attempt and output: " + case_id)
    return " ".join(token if token.startswith('"$') else shlex.quote(token)
                    for token in tokens)


def build(folder=HERE):
    folder = Path(folder)
    manifest_path = folder / "execution-manifest.json"
    manifest = json.loads(manifest_path.read_text())
    plan_path = folder / "case-plan.json"
    plan = json.loads(plan_path.read_text())
    index = json.loads((folder / "aggregate-saved/index.json").read_text())
    manifest_hash = digest(manifest_path)
    assignment = manifest["assignment_id"]
    if (manifest.get("format") != "worker-execution-manifest" or
            assignment != plan["assignment_id"] or index["assignment_id"] != assignment or
            index["manifest_sha256"] != manifest_hash):
        raise ValueError("Queue source identities or saved manifest hash differ")
    selected = [row["case_id"] for row in plan["cases"]]
    entries = {row["case_id"]: row for row in manifest["cases"]}
    saved = {row["case_id"]: row for row in index["cases"]}
    if (len(selected) != len(set(selected)) or len(entries) != len(manifest["cases"])
            or len(saved) != len(index["cases"])
            or set(selected) != set(entries) or set(selected) != set(saved)):
        raise ValueError("Queue selected case, manifest and saved receipts differ")
    rows = []
    for order, case_id in enumerate(selected, 1):
        entry, source = entries[case_id], saved[case_id]
        if digest(folder / entry["construction"]) != entry["construction_sha256"]:
            raise ValueError("Queue construction hash changed: " + case_id)
        receipt = folder / source["receipt"]
        if (digest(receipt) != source["sha256"] or
                digest(folder / source["log"]) != source["log_sha256"]):
            raise ValueError("Queue saved receipt or log changed: " + case_id)
        proof = json.loads(receipt.read_text())
        if (proof["case_id"] != case_id or proof["manifest_sha256"] != manifest_hash or
                proof["construction_sha256"] != entry["construction_sha256"] or
                proof.get("passed") is not True or proof.get("originals_preserved") is not True or
                proof.get("missing_evidence") is not False):
            raise ValueError("Queue selected saved proof failed or is stale: " + case_id)
        candidates = {}
        for candidate in entry.get("candidates", []):
            if digest(folder / candidate["construction"]) != candidate["construction_sha256"]:
                raise ValueError("Queue fallback construction changed: " + case_id)
            candidates[candidate["id"]] = (
                f'.venv-cpu/bin/python runtime.py capture --manifest work/{assignment}/execution-manifest.json '
                f'--case {case_id} --candidate {candidate["id"]} --output "$ATTEMPT" '
                '--host "$CARLA_HOST" --port "$CARLA_PORT" --python "$CARLA_PYTHON"'
            )
        post = entry.get("post_capture", {})
        if post.get("recorded_only") is not True or case_id not in post.get("command", ""):
            raise ValueError("Queue lacks exact saved-only processing: " + case_id)
        rows.append({
            "order": order, "assignment_id": assignment, "case_id": case_id,
            "construction_sha256": entry["construction_sha256"],
            "saved_receipt": source["receipt"], "saved_receipt_sha256": source["sha256"],
            "capture_command": (
                f'.venv-cpu/bin/python runtime.py capture --manifest work/{assignment}/execution-manifest.json '
                f'--case {case_id} --output "$ATTEMPT" --host "$CARLA_HOST" '
                '--port "$CARLA_PORT" --python "$CARLA_PYTHON"'
            ),
            "candidate_commands": candidates,
            "postprocessing_command": post["command"],
            "additional_source_audit_command": local_audit_command(
                entry["delivery_acceptance"], case_id),
            "candidate_selection_rule": "Select only on the declared physical-risk trigger.",
        })
    comparisons = []
    for comparison in plan["comparisons"]:
        if not set(comparison["case_ids"]) <= set(selected):
            raise ValueError("Queue comparison refers to an unselected case")
        comparisons.append({"comparison_id": comparison["comparison_id"],
                            "case_ids": comparison["case_ids"],
                            "audit_command": (
                                f'.venv-cpu/bin/python work/{assignment}/saved_comparison_audit.py '
                                f'--comparison {comparison["comparison_id"]} '
                                f'--output "$COMPARISON_AUDIT_OUTPUT"')})
    return {"format": "worker-assignment-ordered-gpu-queue",
            "assignment_id": assignment, "execution_manifest_sha256": manifest_hash,
            "case_plan_sha256": digest(plan_path),
            "saved_index_sha256": digest(folder / "aggregate-saved/index.json"),
            "cases": rows, "comparisons": comparisons,
            "physical_or_legal_acceptance_claimed": False}


if __name__ == "__main__":
    result = build()
    output = HERE / "gpu-queue.json"
    output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"cases": len(result["cases"]), "comparisons": len(result["comparisons"]),
                      "sha256": digest(output)}))
