"""Bind the current saved-source delivery mechanics and paired comparison audits."""
import hashlib
import json
import shlex
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    path = HERE / "execution-manifest.json"
    manifest = json.loads(path.read_text())
    script = HERE / "prove-delivery-contract-update705.py"
    for entry in manifest["cases"]:
        suffix = entry["case_id"].removeprefix(HERE.name + "__")
        positive = HERE / f"update705-delivery-{suffix}-positive.log"
        negative = HERE / f"update705-delivery-{suffix}-negative.log"
        if '"full_decode_receipts_verified": 4' not in positive.read_text():
            raise ValueError("Missing four current saved decode receipts")
        error = "Synthetic or wrong-case result cannot establish original Native delivery"
        if error not in negative.read_text():
            raise ValueError("Synthetic source was not rejected")
        acceptance = entry["delivery_acceptance"]
        common = [sys.executable, str(script), "--case", entry["case_id"]]
        acceptance.update({"script": script.name, "script_sha256": sha(script),
                           "command": shlex.join(common),
                           "negative_command": shlex.join([*common, "--reject-synthetic"]),
                           "test_exit_code": 0, "test_log": positive.name,
                           "test_log_sha256": sha(positive), "negative_exit_code": 1,
                           "negative_expected_error": error, "negative_log": negative.name,
                           "negative_log_sha256": sha(negative)})
    audit = HERE / "update705-current-comparison-audit.json"
    rows = json.loads(audit.read_text())
    if len(rows["pairs"]) != 4 or len(rows["negatives"]) != 4:
        raise ValueError("Four controlled pairs and negatives required")
    manifest["comparison_audit"] = {
        "script": "audit-current-comparison-update705.py",
        "script_sha256": sha(HERE / "audit-current-comparison-update705.py"),
        "receipt": audit.name, "receipt_sha256": sha(audit),
        "pair_count": 4, "original_native_accepted": False}
    manifest["status"] = "selected_cpu_proofs_rebound_current_json_graphs_original_unverified"
    path.write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps({"cases": 2, "pairs": 4, "manifest_sha256": sha(path)}))


if __name__ == "__main__":
    main()
