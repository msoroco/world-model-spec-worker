"""Run independent CPU diagnostic positive and missing-map checks for four cases."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    script = ROOT / "delivery_audit.py"
    results = []
    for case in json.loads((ROOT / "case-plan.json").read_text())["cases"]:
        cid = case["case_id"]
        short = cid.split("__")[-1]
        attempt = REPO / ".runtime-work/c229435-owner/compat-selected" / short / "primary"
        folder = ROOT / "cases" / short
        positive = REPO / ".runtime-work/c229435-owner/proof" / ("independent-" + short + ".json")
        positive.parent.mkdir(parents=True, exist_ok=True)
        command = [str(REPO / ".venv-cpu/bin/python"), str(script),
                   "--attempt", str(attempt), "--case-id", cid,
                   "--output", str(positive), "--diagnostic"]
        completed = subprocess.run(command, capture_output=True, text=True,
                                   env=os.environ)
        positive_log = folder / "cpu-independent-positive.log"
        positive_log.write_text((completed.stdout + completed.stderr).rstrip() + "\n")
        row = {"case_id": cid, "positive_exit_code": completed.returncode,
               "positive_command": " ".join(command),
               "positive_log": str(positive_log.relative_to(ROOT)),
               "positive_log_sha256": _sha(positive_log)}
        if completed.returncode == 0:
            receipt = folder / "cpu-independent-positive.json"
            receipt.write_bytes(positive.read_bytes())
            row.update({"positive_receipt": str(receipt.relative_to(ROOT)),
                        "positive_receipt_sha256": _sha(receipt)})
        negative = REPO / ".runtime-work/c229435-owner/independent-negative" / short
        if negative.exists():
            shutil.rmtree(negative)
        shutil.copytree(attempt, negative, copy_function=os.link)
        (negative / "original-rail-observations.json").unlink()
        negative_output = REPO / ".runtime-work/c229435-owner/proof" / (
            "independent-negative-" + short + ".json")
        negative_command = [str(REPO / ".venv-cpu/bin/python"), str(script),
            "--attempt", str(negative), "--case-id", cid,
            "--output", str(negative_output), "--diagnostic"]
        failed = subprocess.run(negative_command, capture_output=True, text=True,
                                env=os.environ)
        negative_log = folder / "cpu-independent-negative.log"
        negative_log.write_text((failed.stdout + failed.stderr).rstrip() + "\n")
        row.update({"negative_exit_code": failed.returncode,
            "negative_command": " ".join(negative_command),
            "negative_log": str(negative_log.relative_to(ROOT)),
            "negative_log_sha256": _sha(negative_log),
            "negative_expected_error": "Missing required source: original-rail-observations.json"})
        results.append(row)
        print(short, completed.returncode, failed.returncode, flush=True)
    (ROOT / "cpu-independent-proofs.json").write_text(
        json.dumps(results, indent=2, sort_keys=True) + "\n")
    if any(row["positive_exit_code"] or row["negative_exit_code"] == 0 or
           row["negative_expected_error"] not in (ROOT / row["negative_log"]).read_text()
           for row in results):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
