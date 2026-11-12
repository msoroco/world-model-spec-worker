"""Replay every linked comparison on the exact selected saved attempts."""

from hashlib import sha256
import json
from pathlib import Path
import shlex

from comparison_dispatch import dispatch

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def digest(path):
    return sha256(Path(path).read_bytes()).hexdigest()


def sources():
    manifest = json.loads((HERE / "execution-manifest.json").read_text())
    by_case = {}
    for proof_path in HERE.glob("*saved-proof.json"):
        proof = json.loads(proof_path.read_text())
        tokens = shlex.split(proof["command"])
        case = tokens[tokens.index("--case") + 1]
        attempt = Path(tokens[tokens.index("--attempt") + 1])
        if (proof["case_id"] != case or
                proof["manifest_sha256"] != digest(HERE / "execution-manifest.json") or
                proof["exit_code"] != 0 or
                proof["originals_preserved"] is not True or
                proof["missing_evidence"] is not False or
                digest(HERE / proof["log"]) != proof["log_sha256"]):
            raise ValueError("Saved proof is stale or failed: " + case)
        if case in by_case:
            raise ValueError("Duplicate saved proof: " + case)
        by_case[case] = (attempt, proof_path)
    if set(by_case) != {row["case_id"] for row in manifest["cases"]}:
        raise ValueError("Selected saved proof coverage differs")
    return by_case


def prove():
    by_case = sources()
    plan = json.loads((HERE / "case-plan.json").read_text())
    rows = []
    for comparison in plan["comparisons"]:
        cases = comparison["case_ids"]
        attempts = [by_case[case][0] for case in cases]
        result = dispatch(comparison["comparison_id"], attempts)
        rows.append({"comparison_id": comparison["comparison_id"],
                     "case_ids": cases, "exit_code": 0,
                     "saved_proof_sha256": [digest(by_case[case][1]) for case in cases],
                     "source_result": result["source_audit"]})
    first = plan["comparisons"][0]
    reversed_attempts = [by_case[case][0] for case in reversed(first["case_ids"])]
    try:
        dispatch(first["comparison_id"], reversed_attempts)
    except ValueError as error:
        if "wrong exact case" not in str(error):
            raise
        rejection = str(error)
    else:
        raise ValueError("Swapped selected attempts passed comparison dispatch")
    return {"format": "worker-linked-comparison-dispatch-proof",
            "assignment_id": plan["assignment_id"],
            "manifest_sha256": digest(HERE / "execution-manifest.json"),
            "case_plan_sha256": digest(HERE / "case-plan.json"),
            "dispatcher_sha256": digest(HERE / "comparison_dispatch.py"),
            "comparisons": rows, "negative_exit_code": 1,
            "negative_rejection": rejection,
            "physical_or_legal_acceptance_claimed": False}


if __name__ == "__main__":
    result = prove()
    output = HERE / "comparison-dispatch-proof.json"
    output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"comparisons": len(result["comparisons"]),
                      "negative_rejection": result["negative_rejection"],
                      "sha256": digest(output)}))
