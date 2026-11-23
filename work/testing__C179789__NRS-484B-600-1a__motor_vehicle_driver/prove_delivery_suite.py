"""Run exact positive and negative independent delivery diagnostics."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
SCRIPT = ROOT / "prove_delivery_audit_cases.py"
EXPECTED = "original capture seal, source or restoration differs"


def main() -> None:
    manifest = json.loads((ROOT / "execution-manifest.json").read_text())
    cases = manifest["cases"]
    if len(cases) != 7:
        raise ValueError("seven exact cases required")
    for entry in cases:
        case = entry["case_id"]
        suffix = case.removeprefix(ROOT.name + "__")
        if suffix == case:
            raise ValueError("foreign case")
        folder = ROOT / "delivery" / suffix
        folder.mkdir(parents=True, exist_ok=True)
        for negative in (False, True):
            mode = "negative" if negative else "positive"
            command = [sys.executable, str(SCRIPT), case]
            if negative:
                command.append("--negative")
            result = subprocess.run(command, cwd=REPO, capture_output=True,
                                    text=True, timeout=120)
            log = folder / (mode + ".log")
            log.write_text(result.stdout + result.stderr)
            if result.returncode != (1 if negative else 0):
                raise ValueError("delivery audit " + mode + " exit differs: " + case)
            if negative and EXPECTED not in log.read_text():
                raise ValueError("delivery negative did not reject restoration: " + case)
            if not negative and "independent synthetic source and decode audit passed" not in log.read_text():
                raise ValueError("delivery positive proof missing: " + case)
            print(case, mode, hashlib.sha256(log.read_bytes()).hexdigest(), flush=True)


if __name__ == "__main__":
    main()
