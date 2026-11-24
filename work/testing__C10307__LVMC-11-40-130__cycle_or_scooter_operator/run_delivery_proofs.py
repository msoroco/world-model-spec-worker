"""Record exact-case positive and negative CPU audit-checker proofs."""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
from pathlib import Path

OWN = Path(__file__).resolve().parent
REPO = OWN.parents[1]
MANIFEST = OWN / "execution-manifest.json"
PYTHON = REPO / ".venv-cpu/bin/python"
CHECKS = ["native_source", "all_participants", "time_join", "full_video_decode",
          "actual_pixels", "physical_completion"]
EXPECTED = "independent physical review lacks required positive checks"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(command: list[str], log: Path) -> int:
    with log.open("w") as stream:
        process = subprocess.run(command, cwd=REPO, env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"),
                                 stdout=stream, stderr=subprocess.STDOUT, timeout=30)
    return process.returncode


def main() -> None:
    manifest = json.loads(MANIFEST.read_text())
    for entry in manifest["cases"]:
        case = entry["case_id"]
        short = case.removeprefix(manifest["assignment_id"] + "__")
        command = [str(PYTHON), str(OWN / "prove_delivery_acceptance.py"), "--case", case]
        positive_log = OWN / f"cpu-delivery-check-{short}.log"
        positive_exit = run(command, positive_log)
        negative = [*command, "--negative"]
        negative_log = OWN / f"cpu-delivery-negative-{short}.log"
        negative_exit = run(negative, negative_log)
        if positive_exit != 0 or negative_exit == 0 or EXPECTED not in negative_log.read_text():
            raise RuntimeError("audit checker proof failed for " + short)
        entry["delivery_acceptance"] = {
            "case_id": case, "sets": ["full-test"], "checks": CHECKS,
            "script": "delivery_audit.py", "script_sha256": sha(OWN / "delivery_audit.py"),
            "command": " ".join(command), "test_exit_code": positive_exit,
            "test_log": positive_log.name, "test_log_sha256": sha(positive_log),
            "negative_command": " ".join(negative), "negative_exit_code": negative_exit,
            "negative_expected_error": EXPECTED, "negative_log": negative_log.name,
            "negative_log_sha256": sha(negative_log),
            "scope": "CPU synthetic checker test only; physical source review pending"
        }
        print(short, "delivery checker positive and negative passed", flush=True)
    MANIFEST.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main()
