"""Exercise diagnostic delivery protocols and strict CLI rejection per case."""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

from build_case_plan import KINDS
from independent.delivery_audit import verify
from tests.test_delivery_audit import attempt

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]


def main() -> None:
    base = REPO / ".runtime-work" / ("c153046-delivery-protocol-" +
           datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%f"))
    base.mkdir(parents=True)
    rows = []
    all_passed = True
    for suffix in KINDS:
        folder = base / suffix
        case_id = attempt(folder, suffix)
        protocol = verify(case_id, folder, allow_diagnostic=True)
        command = [sys.executable, str(ROOT / "independent" / "delivery_audit.py"),
                   "--case", case_id, "--attempt", str(folder),
                   "--output", str(folder / "rejected.json"),
                   "--job-id", "synthetic-protocol", "--attempt-number", "1",
                   "--recording-id", "synthetic-protocol"]
        negative = subprocess.run(command, cwd=REPO,
                                  env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"),
                                  text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        rejected = negative.returncode != 0 and "diagnostic fixture cannot pass delivery acceptance" in negative.stdout
        passed = protocol["passed"] is True and protocol["physical_acceptance_claimed"] is False
        all_passed = all_passed and passed and rejected
        rows.append({"case_id": case_id, "diagnostic_protocol_passed": passed,
                     "strict_cli_exit_code": negative.returncode,
                     "strict_cli_expected_error": "diagnostic fixture cannot pass delivery acceptance",
                     "strict_cli_rejected": rejected,
                     "audit_source_sha256": hashlib.sha256((ROOT / "independent" / "delivery_audit.py").read_bytes()).hexdigest()})
        print(suffix, "diagnostic protocol", passed, "strict CLI rejected", rejected)
    receipt = {"format": "c153046-delivery-audit-cpu-protocol-proof",
               "all_passed": all_passed, "physical_acceptance_claimed": False,
               "cases": rows}
    (ROOT / "cpu-delivery-proof.json").write_text(json.dumps(receipt, indent=2) + "\n")
    if not all_passed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
