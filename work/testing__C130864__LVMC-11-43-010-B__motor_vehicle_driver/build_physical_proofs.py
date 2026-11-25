"""Build selected diagnostic physical and lifecycle CPU receipts."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
ASSIGNMENT = ROOT.name
TEMP = REPO / ".runtime-work/c130864-physical-output"
KINDS = ("complete_motion", "incomplete_motion", "missing_evidence")
EVENTS = ("capture_finished", "encoders_closed", "restoration_verified",
          "native_exit", "owner_released", "saved_processing_started")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True,
                               allow_nan=False) + "\n")


def run(command: list[str], log: Path, env: dict[str, str]) -> int:
    completed = subprocess.run(command, cwd=REPO, env=env,
                               capture_output=True, text=True)
    body = (completed.stdout + completed.stderr).rstrip() + "\n"
    log.write_text(body)
    return completed.returncode


def build() -> None:
    TEMP.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ)
    env["SCENARIO_PIPELINE_OUTPUT_ROOT"] = str(TEMP / "pipeline-output")
    env["TMPDIR"] = str(TEMP)
    manifest_path = ROOT / "execution-manifest.json"
    manifest = json.loads(manifest_path.read_text())
    for entry in manifest["cases"]:
        suffix = entry["case_id"].split("__")[-1]
        attempt = REPO / ".runtime-work/c130864-compat-selected" / suffix / "primary"
        if not attempt.is_dir():
            raise ValueError("missing source-shaped diagnostic attempt: " + suffix)
        physical = ROOT / "cases" / suffix / "physical"
        physical.mkdir(exist_ok=True)
        fixtures = []
        for kind in KINDS:
            result = physical / (kind + ".json")
            log = physical / (kind + ".log")
            command = [sys.executable, str(ROOT / "physical_probe.py"),
                       "--attempt", str(attempt), "--kind", kind,
                       "--output", str(result)]
            code = run(command, log, env)
            if code:
                raise RuntimeError(log.read_text())
            observed = json.loads(result.read_text())
            status = observed["physical_checks"]["maneuver"]["status"]
            if status != {"complete_motion": "met",
                          "incomplete_motion": "not_met",
                          "missing_evidence": "unverified"}[kind]:
                raise ValueError("fixture status differs: " + suffix + " " + kind)
            fixtures.append({"kind": kind,
                             "command": " ".join(command),
                             "exit_code": code,
                             "log": str(log.relative_to(ROOT)),
                             "log_sha256": sha(log),
                             "result": str(result.relative_to(ROOT)),
                             "result_sha256": sha(result)})
        life_log = physical / "lifecycle.log"
        life_cmd = [sys.executable, str(ROOT / "lifecycle_probe.py"),
                    "--attempt", str(attempt)]
        code = run(life_cmd, life_log, env)
        if code or tuple(life_log.read_text().splitlines()) != EVENTS:
            raise RuntimeError("lifecycle proof failed: " + life_log.read_text())
        receipt = physical / "receipt.json"
        write(receipt, {"format": "worker-physical-preparation",
                        "case_id": entry["case_id"],
                        "construction_sha256": entry["construction_sha256"],
                        "fixtures": fixtures,
                        "lifecycle": {"command": " ".join(life_cmd),
                                      "diagnostic_fixture": True,
                                      "events": list(EVENTS), "exit_code": 0,
                                      "log": str(life_log.relative_to(ROOT)),
                                      "log_sha256": sha(life_log)},
                        "physical_acceptance_claimed": False,
                        "scope": "synthetic CPU motion outcomes only; reviewed original roundabout site pending"})
        entry["physical_preparation"] = {
            "receipt": str(receipt.relative_to(ROOT)), "sha256": sha(receipt)}
    write(manifest_path, manifest)
    print(json.dumps({"cases": len(manifest["cases"]),
                      "manifest_sha256": sha(manifest_path)}))


if __name__ == "__main__":
    build()
