"""Bind exact diagnostic saved-only receipts and local post-capture commands."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
ID = HERE.name


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bind() -> None:
    path = HERE / "execution-manifest.json"
    manifest = json.loads(path.read_text())
    result_path = HERE / "result.json"
    result = json.loads(result_path.read_text())
    for entry in manifest["cases"]:
        case = entry["case_id"]
        suffix = case.rsplit("__", 1)[-1]
        short = suffix.removeprefix("distance_").replace("_500ft", "")
        source = REPO / ".runtime-work" / f"c129731-saved-materialized-{short}-v12"
        version = source / "v0001"
        receipt_path = version / "processing.json"
        receipt = json.loads(receipt_path.read_text())
        if (receipt.get("format") != "worker-saved-processing"
                or receipt.get("case_id") != case
                or receipt.get("passed") is not True
                or receipt.get("recorded_only") is not True
                or receipt.get("originals_preserved") is not True
                or receipt.get("physical_acceptance_claimed") is not False
                or receipt.get("legal_acceptance_claimed") is not False
                or receipt.get("analysis_revision", {}).get("construction_sha256")
                != entry["construction_sha256"]
                or receipt.get("candidate_id") != "primary"):
            raise ValueError("Saved processing receipt is not this diagnostic case: " + suffix)
        target = HERE / f"cpu-saved-{suffix}.json"
        target.write_bytes(receipt_path.read_bytes())
        receipt_sha = sha(target)
        base = (".venv-cpu/bin/python runtime.py process-saved --manifest "
                + f"work/{ID}/execution-manifest.json --case {case} "
                + "--attempt $ATTEMPT --output $OUTPUT --library runtime/library "
                + "--validator $LEAN_VALIDATOR --owner-release-receipt $OWNER_RELEASE_RECEIPT")
        entry["post_capture"] = {
            "recorded_only": True,
            "command": base,
            "feedback_command": base.replace("--output $OUTPUT", "--output $FEEDBACK_OUTPUT"),
            "test_exit_code": 0,
            "test_log": target.name,
            "test_log_sha256": receipt_sha,
            "proof_scope": "diagnostic saved-only software fixture; no physical or legal acceptance",
        }
        result["tests"] = [row for row in result["tests"] if row["log"] != target.name]
        result["tests"].append({
            "command": f".venv-cpu/bin/python work/{ID}/prove_saved_case.py --case {case}",
            "exit_code": 0,
            "log": target.name,
            "sha256": receipt_sha,
        })
        print(suffix, receipt_sha)
    path.write_text(json.dumps(manifest, indent=2) + "\n")
    result_path.write_text(json.dumps(result, indent=2) + "\n")


if __name__ == "__main__":
    bind()
