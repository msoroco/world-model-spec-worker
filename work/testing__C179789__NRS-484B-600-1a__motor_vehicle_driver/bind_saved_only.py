"""Bind seven current-construction saved-only receipts to the canonical manifest."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
MANIFEST = ROOT / "execution-manifest.json"


def main() -> None:
    manifest = json.loads(MANIFEST.read_text())
    cases = manifest["cases"]
    if len(cases) != 7 or len({entry["case_id"] for entry in cases}) != 7:
        raise ValueError("seven exact cases required")
    for entry in cases:
        case = entry["case_id"]
        suffix = case.removeprefix(ROOT.name + "__")
        if suffix == case:
            raise ValueError("case does not belong to assignment")
        log = ROOT / ("saved-only-processing.json" if suffix == "reference" else
                      "diagnostics/" + suffix + "/saved-only-processing.json")
        receipt = json.loads(log.read_text())
        if (receipt.get("case_id") != case or receipt.get("passed") is not True or
                receipt.get("recorded_only") is not True or
                receipt.get("missing_evidence") is not False or
                receipt.get("originals_preserved") is not True or
                receipt["native_revision"]["construction_sha256"] != entry["construction_sha256"]):
            raise ValueError("current construction lacks saved-only proof: " + case)
        command = ("PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python runtime.py process-saved"
                   " --manifest work/" + ROOT.name + "/execution-manifest.json --case " + case +
                   ' --attempt "$ATTEMPT" --output "$SAVED_OUTPUT" --library "$LIBRARY"'
                   ' --validator "$VALIDATOR" --owner-release-receipt "$OWNER_RELEASE_RECEIPT"')
        entry["post_capture"] = {
            "recorded_only": True,
            "command": command,
            "feedback_command": command,
            "test_log": log.relative_to(ROOT).as_posix(),
            "test_log_sha256": hashlib.sha256(log.read_bytes()).hexdigest(),
            "test_exit_code": 0,
            "proof_scope": "sealed synthetic CPU fixture; original Native capture unreviewed",
        }
    MANIFEST.write_text(json.dumps(manifest, indent=2) + "\n")
    print("seven exact saved-only diagnostic receipts bound")


if __name__ == "__main__":
    main()
