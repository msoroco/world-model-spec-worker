"""Bind tested synthetic outcome and closure receipts to delivery case hashes."""

from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
import subprocess
import sys


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
MANIFEST = HERE / "execution-manifest.json"
OUTPUT = HERE / "physical"
EVENTS = ["capture_finished", "encoders_closed", "restoration_verified",
          "native_exit", "owner_released", "saved_processing_started"]


def digest(path):
    return sha256(Path(path).read_bytes()).hexdigest()


def execute(command, log):
    with Path(log).open("w") as stream:
        subprocess.run(command, cwd=ROOT, stdout=stream, stderr=subprocess.STDOUT,
                       check=True)


def main():
    OUTPUT.mkdir(exist_ok=True)
    manifest = json.loads(MANIFEST.read_text())
    for entry in manifest["cases"]:
        case = entry["case_id"]
        stem = case.rsplit("__", 1)[-1]
        fixtures = []
        for kind in ("complete_motion", "incomplete_motion", "missing_evidence"):
            result = OUTPUT / (stem + "-" + kind + ".json")
            log = OUTPUT / (stem + "-" + kind + ".log")
            command = [sys.executable, str(HERE / "physical_fixture.py"),
                       "--case", case, "--kind", kind, "--output", str(result)]
            execute(command, log)
            value = json.loads(result.read_text())
            if (value.get("case_id") != case or value.get("fixture_kind") != kind
                    or value.get("actual_native_capture") is not False
                    or value.get("physical_acceptance_claimed") is not False):
                raise ValueError("Physical fixture scope or identity changed")
            fixtures.append({"kind": kind, "command": " ".join(command), "exit_code": 0,
                             "log": str(log.relative_to(HERE)), "log_sha256": digest(log),
                             "result": str(result.relative_to(HERE)),
                             "result_sha256": digest(result)})
        lifecycle_log = OUTPUT / (stem + "-lifecycle.log")
        lifecycle_command = [sys.executable, str(HERE / "lifecycle_fixture.py"),
                             "--case", case]
        execute(lifecycle_command, lifecycle_log)
        if " ".join(EVENTS) not in lifecycle_log.read_text():
            raise ValueError("Lifecycle closure events missing or unordered")
        proof = {"construction_sha256": entry["construction_sha256"],
                 "fixture_scope": "Synthetic source protocol and lifecycle only; no actual CARLA capture",
                 "fixtures": fixtures,
                 "lifecycle": {"events": EVENTS, "exit_code": 0,
                               "command": " ".join(lifecycle_command),
                               "log": str(lifecycle_log.relative_to(HERE)),
                               "log_sha256": digest(lifecycle_log)}}
        receipt = OUTPUT / (stem + "-proof.json")
        receipt.write_text(json.dumps(proof, indent=2) + "\n")
        entry["physical_preparation"] = {"receipt": str(receipt.relative_to(HERE)),
                                         "sha256": digest(receipt)}
    MANIFEST.write_text(json.dumps(manifest, indent=2) + "\n")
    print("Bound three physical outcomes and Native closure for", len(manifest["cases"]), "cases")


if __name__ == "__main__":
    main()
