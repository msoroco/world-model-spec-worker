"""Build the ordered local execution commands from the exact case manifest.

This is a preparation artifact.  It does not launch CARLA or claim that a
candidate's physical trigger has occurred.
"""

import json
from hashlib import sha256
from pathlib import Path
import shlex


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
MANIFEST = HERE / "execution-manifest.json"
PLAN = HERE / "case-plan.json"
OUTPUT = HERE / "gpu-queue.json"
SAVED_PROOFS = {
    "same_arrival_ending_yields": "ending-yields-saved-proof.json",
    "same_arrival_ending_enters_first": "ending-enters-first-saved-proof.json",
    "separated_arrival": "separated-arrival-saved-proof.json",
    "official_device_control": "official-device-saved-proof.json",
    "official_device_green_phase": "official-green-saved-proof.json",
    "continuing_highway": "continuing-saved-proof.json",
    **{f"yield_release_delay-{index:04d}":
       f"yield_release_delay-{index:04d}-saved-proof.json" for index in range(3)},
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
        raise ValueError("Delivery audit selects another case: " + case_id)
    for option, value in (("--attempt", '"$ATTEMPT"'),
                          ("--report", '"$ANALYSIS_REPORT"')):
        if option not in tokens or tokens.index(option) + 1 >= len(tokens):
            raise ValueError("Delivery audit lacks exact local source: " + case_id)
        tokens[tokens.index(option) + 1] = value
    return " ".join(token if token.startswith('"$') else shlex.quote(token)
                    for token in tokens)


def build(manifest_path=MANIFEST, plan_path=PLAN):
    manifest_path, plan_path = Path(manifest_path), Path(plan_path)
    manifest, plan = json.loads(manifest_path.read_text()), json.loads(plan_path.read_text())
    assignment = manifest["assignment_id"]
    if assignment != plan["assignment_id"] or manifest.get("format") != "worker-execution-manifest":
        raise ValueError("Queue manifest and case plan identity differ")
    selected = [case["case_id"] for case in plan["cases"]]
    entries = manifest["cases"]
    if len(selected) != len(set(selected)) or len(entries) != len(selected) or {
        entry["case_id"] for entry in entries
    } != set(selected):
        raise ValueError("Queue must cover each selected case exactly once")
    by_id = {entry["case_id"]: entry for entry in entries}
    manifest_hash = digest(manifest_path)
    rows = []
    for order, case_id in enumerate(selected, 1):
        entry = by_id[case_id]
        source = manifest_path.parent / entry["construction"]
        if digest(source) != entry["construction_sha256"]:
            raise ValueError("Queue construction hash changed: " + case_id)
        short = case_id.rsplit("__", 1)[-1]
        proof_name = SAVED_PROOFS.get(short)
        if proof_name is None:
            raise ValueError("Queue lacks selected saved proof mapping: " + case_id)
        proof_path = manifest_path.parent / proof_name
        proof = json.loads(proof_path.read_text())
        if (proof.get("case_id") != case_id or proof.get("manifest_sha256") != manifest_hash
                or proof.get("construction_sha256") != entry["construction_sha256"]
                or proof.get("exit_code") != 0 or proof.get("originals_preserved") is not True
                or proof.get("missing_evidence") is not False):
            raise ValueError("Queue selected saved proof is stale or failed: " + case_id)
        if digest(manifest_path.parent / proof["log"]) != proof["log_sha256"]:
            raise ValueError("Queue selected saved log changed: " + case_id)
        candidates = {}
        for candidate in entry.get("candidates", []):
            alternate = manifest_path.parent / candidate["construction"]
            if digest(alternate) != candidate["construction_sha256"]:
                raise ValueError("Queue fallback construction hash changed: " + case_id)
            candidates[candidate["id"]] = (
                f'.venv-cpu/bin/python runtime.py capture --manifest {manifest_path.relative_to(ROOT)} '
                f'--case {case_id} --candidate {candidate["id"]} --output "$ATTEMPT" '
                '--host "$CARLA_HOST" --port "$CARLA_PORT" --python "$CARLA_PYTHON"'
            )
        post = entry.get("post_capture", {})
        if post.get("recorded_only") is not True or case_id not in post.get("command", ""):
            raise ValueError("Queue lacks saved-only postprocessing: " + case_id)
        rows.append({
            "order": order,
            "assignment_id": assignment,
            "case_id": case_id,
            "construction_sha256": entry["construction_sha256"],
            "saved_proof": proof_name,
            "saved_proof_sha256": digest(proof_path),
            "capture_command": (
                f'.venv-cpu/bin/python runtime.py capture --manifest {manifest_path.relative_to(ROOT)} '
                f'--case {case_id} --output "$ATTEMPT" --host "$CARLA_HOST" '
                '--port "$CARLA_PORT" --python "$CARLA_PYTHON"'
            ),
            "candidate_commands": candidates,
            "postprocessing_command": post["command"],
            "additional_source_audit_command": local_audit_command(
                entry["delivery_acceptance"], case_id),
            "candidate_selection_rule": "Use only the candidate's declared physical trigger; preserve the case and comparison variable.",
        })
    comparisons = []
    for item in plan["comparisons"]:
        if not set(item["case_ids"]) <= set(selected):
            raise ValueError("Queue comparison names an unselected case")
        comparisons.append({"comparison_id": item["comparison_id"], "case_ids": item["case_ids"]})
    return {
        "format": "worker-assignment-ordered-gpu-queue",
        "assignment_id": assignment,
        "execution_manifest_sha256": manifest_hash,
        "case_plan_sha256": digest(plan_path),
        "cases": rows,
        "comparisons": comparisons,
        "physical_or_legal_acceptance_claimed": False,
    }


if __name__ == "__main__":
    result = build()
    OUTPUT.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"cases": len(result["cases"]), "comparisons": len(result["comparisons"]),
                      "sha256": digest(OUTPUT)}))
