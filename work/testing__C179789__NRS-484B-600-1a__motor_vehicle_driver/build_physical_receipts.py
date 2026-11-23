"""Run and bind source-backed synthetic physical outcome and lifecycle CPU proofs."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(command: list[str], log: Path) -> None:
    environment = dict(os.environ)
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    environment["SCENARIO_PIPELINE_OUTPUT_ROOT"] = str(
        (ROOT / ".runtime-work/c179789-physical-build").resolve())
    result = subprocess.run(command, cwd=ROOT, env=environment,
                            capture_output=True, text=True)
    log.write_text(result.stdout + result.stderr, encoding="utf-8")
    if result.returncode:
        raise ValueError(f"physical CPU proof failed ({result.returncode}): {log}")


def main() -> None:
    manifest_path = HERE / "execution-manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    lifecycle_log = HERE / "physical-lifecycle.log"
    life_cmd = [sys.executable, str(HERE / "prove_capture_lifecycle.py")]
    run(life_cmd, lifecycle_log)
    events = json.loads(lifecycle_log.read_text(encoding="utf-8"))
    if events["exit_code"] != 0 or events["provenance_kind"] != "synthetic_fixture":
        raise ValueError("lifecycle proof did not identify synthetic provenance")
    for entry in manifest["cases"]:
        case_id = entry["case_id"]
        suffix = case_id.rsplit("__", 1)[-1]
        fixtures = []
        for kind in ("complete_motion", "incomplete_motion", "missing_evidence"):
            output = HERE / "physical" / suffix / kind
            output.mkdir(parents=True, exist_ok=True)
            command = [sys.executable, str(HERE / "prove_physical_completion.py"),
                       "--case", case_id, "--kind", kind, "--output", str(output)]
            log = output / "proof.log"
            run(command, log)
            result = output / "result.json"
            fixtures.append({"kind": kind,
                             "command": "PYTHONDONTWRITEBYTECODE=1 " +
                                        " ".join(command),
                             "exit_code": 0,
                             "log": str(log.relative_to(HERE)),
                             "log_sha256": sha(log),
                             "result": str(result.relative_to(HERE)),
                             "result_sha256": sha(result)})
        receipt = {"format": "c179789-physical-cpu-proof-v1",
                   "case_id": case_id,
                   "construction_sha256": entry["construction_sha256"],
                   "provenance_kind": "synthetic_fixture",
                   "fixtures": fixtures,
                   "lifecycle": {"events": events["events"], "exit_code": 0,
                                 "command": "PYTHONDWRITEBYTECODE=1 " + " ".join(life_cmd),
                                 "log": lifecycle_log.name,
                                 "log_sha256": sha(lifecycle_log)}}
        receipt_path = HERE / "physical" / suffix / "receipt.json"
        receipt_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n",
                                encoding="utf-8")
        entry["physical_preparation"] = {
            "receipt": str(receipt_path.relative_to(HERE)), "sha256": sha(receipt_path)}
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print("Seven case-bound physical CPU proof receipts built from measured synthetic traces")


if __name__ == "__main__":
    main()
