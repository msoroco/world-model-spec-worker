"""Generate exact-case synthetic physical outcome and lifecycle CPU receipts."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
MANIFEST = ROOT / "execution-manifest.json"
SCRIPT = ROOT / "physical_preparation.py"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def dump(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")


def run(case: str, kind: str, result: Path | None, log: Path) -> tuple[str, int]:
    command = [sys.executable, str(SCRIPT.relative_to(REPO)), "--case", case,
               "--kind", kind, "--output", str(result.relative_to(REPO)) if result else ".runtime-work/unused"]
    completed = subprocess.run(command, cwd=REPO, capture_output=True, text=True)
    log.write_text((completed.stdout + completed.stderr).rstrip() + "\n")
    if completed.returncode:
        raise RuntimeError(log.read_text())
    return " ".join(command), completed.returncode


def main() -> None:
    manifest = json.loads(MANIFEST.read_text())
    for entry in manifest["cases"]:
        suffix = entry["case_id"].split("__")[-1]
        fixtures = []
        for kind in ("complete_motion", "incomplete_motion", "missing_evidence"):
            result = ROOT / f"physical-{suffix}-{kind}.json"
            log = ROOT / f"physical-{suffix}-{kind}.log"
            command, exit_code = run(entry["case_id"], kind, result, log)
            fixtures.append({"kind": kind, "command": command, "exit_code": exit_code,
                             "log": log.name, "log_sha256": sha(log),
                             "result": result.name, "result_sha256": sha(result)})
        log = ROOT / f"physical-{suffix}-lifecycle.log"
        command, exit_code = run(entry["case_id"], "lifecycle", None, log)
        receipt = ROOT / f"physical-{suffix}-receipt.json"
        dump(receipt, {"format": "worker-physical-preparation",
                       "case_id": entry["case_id"],
                       "construction_sha256": entry["construction_sha256"],
                       "fixtures": fixtures,
                       "lifecycle": {"events": ["capture_finished", "encoders_closed",
                                                "restoration_verified", "native_exit",
                                                "owner_released", "saved_processing_started"],
                                     "command": command, "exit_code": exit_code,
                                     "log": log.name, "log_sha256": sha(log)}})
        entry["physical_preparation"] = {"receipt": receipt.name, "sha256": sha(receipt)}
        dump(MANIFEST, manifest)
        print("passed", suffix)


if __name__ == "__main__":
    main()
