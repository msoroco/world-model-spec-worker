"""Assemble tested CPU handoff without claiming physical acceptance."""

import json
from pathlib import Path


PACKAGE = Path(__file__).resolve().parent
DRAFT = PACKAGE / "execution-manifest.draft.json"
FINAL = PACKAGE / "execution-manifest.json"


def main():
    manifest = json.loads(DRAFT.read_text())
    saved = {item["case_id"]: item for item in json.loads(
        (PACKAGE / "cpu-saved-proofs.json").read_text())}
    for entry in manifest["cases"]:
        case_id = entry["case_id"]
        proof = saved[case_id]
        if not proof["passed"] or proof["exit_code"] != 0:
            raise ValueError("saved-only CPU proof absent: " + case_id)
        command = (f".venv-cpu/bin/python runtime.py process-saved --manifest "
                   f"work/{PACKAGE.name}/execution-manifest.json --case {case_id} "
                   "--attempt \"$ATTEMPT\" --output \"$SAVED_OUTPUT\" "
                   "--library \"$LIBRARY\" --validator \"$VALIDATOR\" "
                   "--owner-release-receipt \"$OWNER_RELEASE_RECEIPT\"")
        entry["post_capture"] = {
            "recorded_only": True, "command": command, "feedback_command": command,
            "test_exit_code": 0, "test_log": proof["log"],
            "test_log_sha256": proof["log_sha256"],
            "proof_scope": "Synthetic diagnostic saved-only processing; original Native review pending"}
    manifest["status"] = "cpu_prepared"
    FINAL.write_text(json.dumps(manifest, sort_keys=True, indent=2) + "\n")
    print("finalized", len(manifest["cases"]), "exact CPU-prepared cases")


if __name__ == "__main__":
    main()
