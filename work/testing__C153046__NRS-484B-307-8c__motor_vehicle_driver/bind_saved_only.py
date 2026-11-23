"""Bind eight pinned saved-only fixture proofs to exact manifest cases."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from build_case_plan import AID, KINDS

ROOT = Path(__file__).resolve().parent
MANIFEST = ROOT / "execution-manifest.json"


def main() -> None:
    manifest = json.loads(MANIFEST.read_text())
    expected = {AID + "__" + suffix for suffix in KINDS}
    cases = {entry["case_id"]: entry for entry in manifest["cases"]}
    if len(cases) != len(manifest["cases"]) or set(cases) != expected:
        raise ValueError("exact eight-case manifest required")
    for suffix in KINDS:
        case = AID + "__" + suffix
        log = ROOT / "diagnostics" / suffix / "saved-only-processing.json"
        receipt = json.loads(log.read_text())
        if (receipt.get("case_id") != case or receipt.get("passed") is not True or
                receipt.get("recorded_only") is not True or
                receipt.get("missing_evidence") is not False or
                receipt["native_revision"]["construction_sha256"] != cases[case]["construction_sha256"]):
            raise ValueError("current construction lacks saved-only receipt: " + case)
        command = ("PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python runtime.py process-saved"
                   " --manifest work/" + AID + "/execution-manifest.json --case " + case +
                   ' --attempt "$ATTEMPT" --output "$SAVED_OUTPUT" --library "$LIBRARY"'
                   ' --validator "$VALIDATOR" --owner-release-receipt "$OWNER_RELEASE_RECEIPT"')
        cases[case]["post_capture"] = {
            "recorded_only": True,
            "command": command,
            "feedback_command": command,
            "test_log": log.relative_to(ROOT).as_posix(),
            "test_log_sha256": hashlib.sha256(log.read_bytes()).hexdigest(),
            "test_exit_code": 0,
            "proof_scope": "sealed synthetic CPU fixture only; original Native capture unreviewed",
        }
    MANIFEST.write_text(json.dumps(manifest, indent=2) + "\n")
    print("eight exact saved-only diagnostic receipts bound")


if __name__ == "__main__":
    main()
