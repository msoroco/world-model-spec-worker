"""Replay selected synthetic acquisitions through recorded-only processing."""

import json
import os
from pathlib import Path
import subprocess
import sys


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
MANIFEST = HERE / "execution-manifest.selected-draft.json"
SCRATCH = ROOT / ".runtime-work" / "c228989-owner-nov26"
VALIDATOR = ROOT / ".runtime-work" / "c110969-decoder" / ".lake" / "build" / "bin" / "adapterCheck"


def run():
    entries = json.loads(MANIFEST.read_text(encoding="utf-8"))["cases"]
    for entry in entries:
        suffix = entry["case_id"].removeprefix(HERE.name + "__")
        attempt = SCRATCH / "selected-compat-v3" / suffix
        destination = SCRATCH / "selected-saved-v3" / suffix
        if destination.exists():
            raise ValueError("retain prior saved processing proof")
        command = [sys.executable, str(ROOT / "runtime.py"), "process-saved",
                   "--manifest", str(MANIFEST), "--case", entry["case_id"],
                   "--attempt", str(attempt), "--output", str(destination),
                   "--library", str(ROOT / "runtime" / "library"),
                   "--validator", str(VALIDATOR)]
        env = dict(os.environ)
        env["SCENARIO_PIPELINE_OUTPUT_ROOT"] = str(SCRATCH)
        env["TMPDIR"] = str(SCRATCH)
        result = subprocess.run(command, cwd=ROOT, env=env, text=True,
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        log = HERE / ("proof-selected-saved-" + suffix + ".log")
        log.write_text(result.stdout.rstrip() + "\n", encoding="utf-8")
        if result.returncode:
            raise ValueError("selected recorded-only proof failed: " + entry["case_id"])
        receipt = json.loads(result.stdout)
        if not (receipt.get("passed") is True and receipt.get("recorded_only") is True and
                receipt.get("originals_preserved") is True and receipt.get("missing_evidence") is False):
            raise ValueError("saved-only replay did not preserve full source evidence")
    return len(entries)


if __name__ == "__main__":
    print("selected saved-only proofs:", run())
