"""Exercise three probe cases through the frozen saved-only processor."""

from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
import shutil
import subprocess
import sys
from time import time_ns


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
MANIFEST = HERE / "delivery-construction-manifest.json"
VALIDATOR = ROOT / ".runtime-work/fire-decoder/.lake/build/bin/adapterCheck"


def digest(path):
    return sha256(Path(path).read_bytes()).hexdigest()


def run(command, log):
    with Path(log).open("w") as output:
        subprocess.run(command, cwd=ROOT, stdout=output, stderr=subprocess.STDOUT,
                       check=True)


def main():
    entries = json.loads(MANIFEST.read_text())["cases"]
    proofs = []
    for entry in entries:
        case = entry["case_id"]
        suffix = case.rsplit("__", 1)[-1]
        stamp = str(time_ns())
        prefix = ROOT / ".runtime-work" / ("c147331-delivery-saved-" + suffix + "-" + stamp)
        fixture, attempt, processed = (Path(str(prefix) + ending)
                                       for ending in ("-fixture", "-attempt", "-processing"))
        run([sys.executable, "runtime.py", "fixture", "--recipe",
             str(ROOT / entry["fixture_recipe"]), "--output", str(fixture)],
            HERE / ("delivery-" + suffix + "-fixture-command.log"))
        run([sys.executable, "runtime.py", "materialize", "--manifest", str(MANIFEST),
             "--case", case, "--output", str(attempt)],
            HERE / ("delivery-" + suffix + "-materialize-command.log"))
        for path in fixture.iterdir():
            target = attempt / path.name
            if target.exists():
                raise ValueError("Diagnostic source shadows construction: " + path.name)
            if path.is_dir():
                shutil.copytree(path, target)
            else:
                shutil.copy2(path, target)
        command = [sys.executable, "runtime.py", "process-saved", "--manifest",
                   str(MANIFEST), "--case", case, "--attempt", str(attempt),
                   "--output", str(processed), "--library", "runtime/library",
                   "--validator", str(VALIDATOR)]
        log = HERE / ("delivery-" + suffix + "-saved-processing-command.log")
        run(command, log)
        receipt_path = processed / "v0001" / "processing.json"
        receipt = json.loads(receipt_path.read_text())
        if (receipt.get("passed") is not True or receipt.get("missing_evidence") is not False
                or receipt.get("originals_preserved") is not True
                or receipt.get("analysis_revision", {}).get("construction_sha256")
                != entry["construction_sha256"]):
            raise ValueError("Saved delivery processing incomplete: " + suffix)
        proofs.append({"case_id": case, "construction_sha256": entry["construction_sha256"],
                       "command": " ".join(command), "exit_code": 0,
                       "log": log.name, "log_sha256": digest(log),
                       "receipt_sha256": digest(receipt_path), "originals_preserved": True,
                       "missing_evidence": False, "physical_acceptance_claimed": False})
    (HERE / "delivery-saved-proofs.json").write_text(json.dumps({
        "format": "worker-lane-delivery-saved-proofs", "delivery_ready": False,
        "manifest_sha256": digest(MANIFEST), "cases": proofs}, indent=2) + "\n")


if __name__ == "__main__":
    main()
