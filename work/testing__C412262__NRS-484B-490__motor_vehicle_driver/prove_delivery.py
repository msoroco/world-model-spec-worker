"""Exercise each source-bound diagnostic audit and missing-context rejection."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
SCRATCH = REPO / ".runtime-work/c412262-490-delivery"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def output_of(command: str) -> Path:
    tokens = shlex.split(command)
    return Path(tokens[tokens.index("--output") + 1])


def write_log(path: Path, run: subprocess.CompletedProcess) -> None:
    message = (run.stdout + run.stderr).rstrip() or (
        "diagnostic source audit exited " + str(run.returncode))
    path.write_text(message + "\n", encoding="utf-8")


def main() -> None:
    SCRATCH.mkdir(parents=True, exist_ok=True)
    manifest = json.loads((ROOT / "execution-manifest.json").read_text())
    results = []
    for entry in manifest["cases"]:
        case_id = entry["case_id"]
        tag = case_id.rsplit("__", 1)[1]
        attempt = output_of(entry["compatibility"]["command"])
        command = [sys.executable, str(ROOT / "diagnostic_delivery_audit.py"),
                   "--diagnostic", "--case", case_id, "--attempt", str(attempt),
                   "--output", str(SCRATCH / (tag + "-positive.json"))]
        Path(command[-1]).unlink(missing_ok=True)
        run = subprocess.run(command, cwd=REPO, env=os.environ, text=True, capture_output=True)
        positive_log = ROOT / ("cpu-delivery-" + tag + "-positive.log")
        write_log(positive_log, run)
        if run.returncode:
            raise RuntimeError(case_id + ": " + positive_log.read_text()[-2000:])
        receipt = ROOT / ("cpu-delivery-" + tag + "-positive.json")
        receipt.write_bytes(Path(command[-1]).read_bytes())
        missing = SCRATCH / (tag + "-missing-context")
        missing.mkdir(exist_ok=True)
        negative_command = [sys.executable, str(ROOT / "diagnostic_delivery_audit.py"),
            "--diagnostic", "--case", case_id, "--attempt", str(missing),
            "--output", str(SCRATCH / (tag + "-negative.json"))]
        failed = subprocess.run(negative_command, cwd=REPO, env=os.environ, text=True, capture_output=True)
        negative_log = ROOT / ("cpu-delivery-" + tag + "-negative.log")
        write_log(negative_log, failed)
        expected = "Missing required source: context.json"
        if failed.returncode == 0 or expected not in negative_log.read_text():
            raise RuntimeError(case_id + ": missing exact context was not rejected")
        results.append({"case_id": case_id, "command": shlex.join(command),
                        "positive_exit_code": 0, "positive_log": positive_log.name,
                        "positive_log_sha256": sha(positive_log),
                        "positive_receipt": receipt.name, "positive_receipt_sha256": sha(receipt),
                        "negative_command": shlex.join(negative_command),
                        "negative_exit_code": failed.returncode,
                        "negative_log": negative_log.name,
                        "negative_log_sha256": sha(negative_log),
                        "negative_expected_error": expected,
                        "diagnostic_fixture": True})
        print(tag, "independent diagnostic source audit passed", flush=True)
    (ROOT / "cpu-delivery-proofs.json").write_text(
        json.dumps(results, sort_keys=True, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
