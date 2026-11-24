"""Return seven current-byte recorded-only processing receipts."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    manifest_path = HERE / "execution-manifest.json"
    manifest = json.loads(manifest_path.read_text())
    for entry in manifest["cases"]:
        case_id = entry["case_id"]
        suffix = case_id.removeprefix(HERE.name + "__")
        root = REPO / ".runtime-work/c109035-saved-proof" / suffix
        receipt_path = root / "versions/v0001/processing.json"
        receipt = json.loads(receipt_path.read_text())
        construction = json.loads((HERE / entry["construction"]).read_text())
        analysis = next(item["content"] for item in construction["files"]
                        if item["path"] == "analysis.py")
        expected_analysis = hashlib.sha256(analysis.encode()).hexdigest()
        if (receipt.get("case_id") != case_id or
                receipt.get("passed") is not True or
                receipt.get("recorded_only") is not True or
                receipt.get("originals_preserved") is not True or
                receipt.get("physical_acceptance_claimed") is not False or
                receipt["native_revision"]["construction_sha256"] !=
                sha(root / "attempt/construction.json") or
                receipt["native_revision"]["analyzer_sha256"] != expected_analysis):
            raise ValueError("Saved-only receipt differs from selected bytes: " + suffix)
        target = HERE / "saved-proofs" / (suffix + "-processing.json")
        target.parent.mkdir(exist_ok=True)
        target.write_text(json.dumps(receipt, indent=2) + "\n")
        entry["saved_only"] = {"receipt": target.relative_to(HERE).as_posix(),
                               "sha256": sha(target),
                               "proof_log": f"cpu-saved-{suffix}-v9.log",
                               "proof_log_sha256": sha(HERE / f"cpu-saved-{suffix}-v9.log")}
        command = ("PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python runtime.py process-saved "
                   "--manifest work/" + HERE.name + "/execution-manifest.json --case " + case_id +
                   ' --attempt "$ATTEMPT" --output "$SAVED_OUTPUT" --library "$LIBRARY"' +
                   ' --validator "$VALIDATOR" --owner-release-receipt "$OWNER_RELEASE_RECEIPT"')
        entry["post_capture"] = {
            "recorded_only": True, "command": command, "feedback_command": command,
            "test_log": f"cpu-saved-{suffix}-v9.log",
            "test_log_sha256": sha(HERE / f"cpu-saved-{suffix}-v9.log"),
            "test_exit_code": 0,
            "proof_scope": "sealed synthetic source fixture; physical Native capture pending"}
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
    print("bound seven current-byte recorded-only processing receipts")


if __name__ == "__main__":
    main()
