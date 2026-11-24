"""Generate and exercise exact-case synthetic physical/lifecycle CPU fixtures."""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
from pathlib import Path

OWN = Path(__file__).resolve().parent
REPO = OWN.parents[1]
PYTHON = REPO / ".venv-cpu/bin/python"
MANIFEST = OWN / "execution-manifest.json"
KINDS = ("complete_motion", "incomplete_motion", "missing_evidence")
EVENTS = ["capture_finished", "encoders_closed", "restoration_verified",
          "native_exit", "owner_released", "saved_processing_started"]


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(command: list[str], log: Path) -> int:
    with log.open("w") as stream:
        return subprocess.run(command, cwd=REPO,
                              env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"),
                              stdout=stream, stderr=subprocess.STDOUT,
                              timeout=30).returncode


def samples(kind: str) -> list[dict]:
    rows = []
    for index in range(900):
        if kind == "missing_evidence" and index == 450:
            continue
        fraction = index / 899
        x = -30 + (60 if kind == "complete_motion" else 30) * fraction
        rows.append({"frame": index, "time_s": (index + 1) / 20,
                     "x_m": round(x, 6), "y_m": -.75,
                     "velocity_mps": 60 / 44.95 if kind == "complete_motion" else 30 / 44.95})
    return rows


def main() -> None:
    manifest = json.loads(MANIFEST.read_text())
    for entry in manifest["cases"]:
        case = entry["case_id"]
        short = case.removeprefix(manifest["assignment_id"] + "__")
        fixture_receipts = []
        for kind in KINDS:
            stem = f"physical-{short}-{kind}"
            spec = OWN / (stem + "-source.json")
            spec.write_text(json.dumps({"case_id": case, "kind": kind,
                                        "samples": samples(kind)}, separators=(",", ":")) + "\n")
            result = OWN / (stem + "-result.json")
            if result.exists():
                result.unlink()
            log = OWN / (stem + ".log")
            command = [str(PYTHON), str(OWN / "physical_fixture_probe.py"),
                       "--spec", str(spec), "--output", str(result)]
            exit_code = run(command, log)
            if exit_code != 0:
                raise RuntimeError(f"physical fixture failed: {stem}: {log.read_text()}")
            expected = {"complete_motion": "met", "incomplete_motion": "not_met",
                        "missing_evidence": "unverified"}[kind]
            if json.loads(result.read_text())["physical_checks"]["maneuver"]["status"] != expected:
                raise RuntimeError("physical fixture status mismatch: " + stem)
            fixture_receipts.append({"kind": kind, "command": " ".join(command),
                                     "exit_code": exit_code, "log": log.name,
                                     "log_sha256": sha(log), "result": result.name,
                                     "result_sha256": sha(result)})
        events = OWN / f"physical-{short}-lifecycle-source.json"
        events.write_text(json.dumps({"events": EVENTS}, indent=2) + "\n")
        life_log = OWN / f"physical-{short}-lifecycle.log"
        life_command = [str(PYTHON), str(OWN / "lifecycle_probe.py"),
                        "--events", str(events)]
        exit_code = run(life_command, life_log)
        if exit_code != 0:
            raise RuntimeError("lifecycle fixture failed: " + short)
        receipt = OWN / f"physical-{short}-receipt.json"
        proof = {"format": "worker-physical-preparation-cpu-proof-v1",
                 "case_id": case, "construction_sha256": entry["construction_sha256"],
                 "fixtures": fixture_receipts,
                 "lifecycle": {"events": EVENTS, "command": " ".join(life_command),
                               "exit_code": exit_code, "log": life_log.name,
                               "log_sha256": sha(life_log)},
                 "scope": "synthetic CPU decision and event-order proof; no Native physical acceptance"}
        receipt.write_text(json.dumps(proof, indent=2) + "\n")
        entry["physical_preparation"] = {"receipt": receipt.name, "sha256": sha(receipt)}
        print(short, "three physical fixtures and lifecycle passed", flush=True)
    MANIFEST.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main()
