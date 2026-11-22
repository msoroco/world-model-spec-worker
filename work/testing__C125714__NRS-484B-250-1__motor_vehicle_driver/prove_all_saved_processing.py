"""Reprocess each saved synthetic diagnostic without touching acquisition."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
SUFFIXES = ("precedence", "advance", "other_later", "opposite_straight",
            "opposite_intends_left", "opposite_makes_left", "wide_same_crossing")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def prove(compat_root, output_root, validator):
    compat_root, output_root = Path(compat_root).resolve(), Path(output_root).resolve()
    if (REPO / ".runtime-work" not in compat_root.parents or
            REPO / ".runtime-work" not in output_root.parents or output_root.exists()):
        raise ValueError("Use retained compatibility and fresh saved roots beneath .runtime-work")
    runtime_output = os.environ.get("SCENARIO_PIPELINE_OUTPUT_ROOT", "")
    if not runtime_output or REPO / ".runtime-work" not in Path(runtime_output).resolve().parents:
        raise ValueError("Export SCENARIO_PIPELINE_OUTPUT_ROOT beneath .runtime-work")
    output_root.mkdir(parents=True)
    for suffix in SUFFIXES:
        folder = ROOT if suffix == "precedence" else ROOT / "cases" / suffix
        case_id = ROOT.name + "__" + suffix
        attempt = compat_root / suffix
        destination = output_root / suffix
        command = [sys.executable, str(REPO / "runtime.py"), "process-saved",
                   "--manifest", str(ROOT / "diagnostic-execution-manifest.json"),
                   "--case", case_id, "--attempt", str(attempt),
                   "--output", str(destination),
                   "--library", str(REPO / "runtime" / "library"),
                   "--validator", str(Path(validator).resolve())]
        log = folder / "diagnostic-saved-processing.log"
        with log.open("w") as stream:
            status = subprocess.run(command, cwd=REPO, env=os.environ,
                                    stdout=stream, stderr=subprocess.STDOUT,
                                    timeout=600).returncode
        if status:
            raise ValueError("Saved processing failed for " + suffix + "; inspect " + str(log))
        receipt_path = destination / "v0001" / "processing.json"
        receipt = json.loads(receipt_path.read_text())
        if (receipt.get("case_id") != case_id or receipt.get("passed") is not True or
                receipt.get("recorded_only") is not True or
                receipt.get("originals_preserved") is not True or
                receipt.get("missing_evidence") is not False or
                receipt.get("physical_acceptance_claimed") is not False or
                receipt.get("legal_acceptance_claimed") is not False or
                receipt.get("timestamp_joins", {}).get("passed") is not True or
                receipt.get("final_video_checks", {}).get("passed") is not True):
            raise ValueError("Saved processing receipt incomplete for " + suffix)
        proof = {"format": "worker-saved-diagnostic-proof", "case_id": case_id,
                 "diagnostic_only": True, "passed": True,
                 "originals_preserved": True, "timestamp_join_frames": receipt["timestamp_joins"]["frames"],
                 "final_video_sha256": receipt["final_video_checks"]["video_sha256"],
                 "construction_sha256": receipt["analysis_revision"]["construction_sha256"],
                 "runtime_manifest_sha256": receipt["analysis_revision"]["runtime_manifest_sha256"],
                 "processing_receipt_sha256": sha(receipt_path),
                 "command_log_sha256": sha(log),
                 "physical_acceptance_claimed": False, "legal_acceptance_claimed": False}
        (folder / "diagnostic-saved-processing-proof.json").write_text(
            json.dumps(proof, indent=2) + "\n")
        print(json.dumps({"case_id": case_id, "saved_processing": "passed",
                          "diagnostic_only": True}), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--compat-root", required=True)
    parser.add_argument("--output-root", required=True)
    parser.add_argument("--validator", required=True)
    args = parser.parse_args()
    prove(args.compat_root, args.output_root, args.validator)
