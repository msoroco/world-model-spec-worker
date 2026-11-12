"""Run one selected delivery audit CPU proof without claiming physical acceptance."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

from source_join_audit import read, require, sha

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
MANIFEST = HERE / "execution-manifest.json"
AUDITOR = HERE / "delivery_audit.py"
RUNS = ROOT / ".runtime-work/c110454-update025-six-selected"
PROOFS = HERE / "update025-selected-proofs"


def run(case: str, *, negative: bool = False) -> dict:
    manifest = read(MANIFEST)
    entry = next((item for item in manifest["cases"] if item["case_id"] == case), None)
    require(entry is not None and entry.get("kind") == "delivery",
            "Delivery case is not selected")
    suffix = case.removeprefix(HERE.name + "__")
    require(suffix in ("rail_reference", "rail_contrast", "oneway_absent",
                       "oneway_present", "traversal_reference", "traversal_contrast"),
            "Unsupported selected delivery suffix")
    attempt = RUNS / suffix / "primary/compatibility"
    processing = PROOFS / suffix / "primary/process-saved.log"
    proof = read(PROOFS / suffix / "primary/proof.json")
    require(proof["manifest_sha256"] == sha(MANIFEST) and
            proof["construction_sha256"] == entry["construction_sha256"] and
            proof["process_saved_log_sha256"] == sha(processing),
            "Selected saved source proof changed")
    require(read(attempt / "candidate-selection.json").get("manifest_sha256") == sha(MANIFEST),
            "Selected attempt uses another manifest")
    with tempfile.TemporaryDirectory(prefix="c110454-delivery-") as directory:
        output = Path(directory) / "audit.json"
        construction = "0" * 64 if negative else entry["construction_sha256"]
        command = [sys.executable, str(AUDITOR), "--case", case,
                   "--candidate", "primary", "--construction-sha256", construction,
                   "--attempt", str(attempt), "--processing", str(processing),
                   "--output", str(output), "--diagnostic"]
        completed = subprocess.run(command, cwd=ROOT, text=True,
                                   stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        if negative:
            require(completed.returncode != 0 and
                    "Delivery construction differs from selected manifest" in completed.stdout and
                    not output.exists(),
                    "Wrong construction failed to reject at independent delivery audit")
            print(completed.stdout, end="")
            return {"case_id": case, "negative_exit_code": completed.returncode,
                    "expected_error": "Delivery construction differs from selected manifest"}
        require(completed.returncode == 0 and output.is_file(),
                "Selected diagnostic delivery audit failed: " + completed.stdout)
        receipt = read(output)
        require(receipt.get("format") == "worker-delivery-audit" and
                receipt.get("case_id") == case and
                receipt.get("candidate_id") == "primary" and
                receipt.get("source_shaped_unit_test") is True and
                receipt.get("passed") is False and
                not any(receipt.get("checks", {}).values()) and
                receipt.get("physical_or_legal_acceptance_claimed") is False,
                "Diagnostic delivery audit promoted a fixture")
        result = {"case_id": case, "auditor_sha256": sha(AUDITOR),
                  "construction_sha256": construction,
                  "source_shape_passed": True, "delivery_accepted": False}
        print(json.dumps(result))
        return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", required=True)
    parser.add_argument("--negative", action="store_true")
    args = parser.parse_args()
    run(args.case, negative=args.negative)
    if args.negative:
        sys.exit(1)
