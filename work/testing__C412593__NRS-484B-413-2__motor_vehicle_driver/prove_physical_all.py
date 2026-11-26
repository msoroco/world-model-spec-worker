"""Bind three synthetic physical outcomes and lifecycle proof to each case."""

from __future__ import annotations

from hashlib import sha256
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
MANIFEST = ROOT / "execution-manifest.json"


def digest(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def relative(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def main() -> None:
    private = Path(os.environ["SCENARIO_PIPELINE_OUTPUT_ROOT"]).resolve()
    if not private.is_relative_to(REPO / ".runtime-work"):
        raise ValueError("physical scratch must be under .runtime-work")
    manifest = json.loads(MANIFEST.read_text())
    env = dict(os.environ, PYTHONPATH=str(REPO / "runtime/scenario_pipeline"))
    for entry in manifest["cases"]:
        tag = entry["case_id"].rsplit("__", 1)[-1]
        folder = ROOT / "cases" / tag / "physical"
        folder.mkdir(parents=True, exist_ok=True)
        fixtures = []
        for kind in ("complete_motion", "incomplete_motion", "missing_evidence"):
            result = folder / (kind + ".json")
            command = [sys.executable, str(ROOT / "prove_physical.py"),
                       "--case", entry["case_id"], "--kind", kind,
                       "--output", str(result)]
            run = subprocess.run(command, cwd=REPO, env=env, text=True,
                                 capture_output=True, check=False)
            log = folder / (kind + ".log")
            log.write_text((run.stdout + run.stderr).rstrip() + "\n")
            if run.returncode:
                raise RuntimeError(f"physical {tag}/{kind}: {run.stderr}")
            fixtures.append({"kind": kind, "command": " ".join(command),
                             "exit_code": 0, "log": relative(log),
                             "log_sha256": digest(log), "result": relative(result),
                             "result_sha256": digest(result)})
        command = [sys.executable, str(ROOT / "prove_lifecycle.py"),
                   "--case", entry["case_id"]]
        run = subprocess.run(command, cwd=REPO, env=env, text=True,
                             capture_output=True, check=False)
        log = folder / "lifecycle.log"
        log.write_text((run.stdout + run.stderr).rstrip() + "\n")
        if run.returncode:
            raise RuntimeError(f"lifecycle {tag}: {run.stderr}")
        receipt = folder / "physical-preparation.json"
        proof = {"format": "c412593-synthetic-physical-preparation",
                 "case_id": entry["case_id"],
                 "construction_sha256": entry["construction_sha256"],
                 "fixtures": fixtures, "physical_acceptance_claimed": False,
                 "lifecycle": {"command": " ".join(command), "exit_code": 0,
                               "log": relative(log), "log_sha256": digest(log),
                               "events": ["capture_finished", "encoders_closed",
                                          "restoration_verified", "native_exit",
                                          "owner_released", "saved_processing_started"]}}
        receipt.write_text(json.dumps(proof, indent=2, sort_keys=True) + "\n")
        entry["physical_preparation"] = {"receipt": relative(receipt),
                                         "sha256": digest(receipt)}
        MANIFEST.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
