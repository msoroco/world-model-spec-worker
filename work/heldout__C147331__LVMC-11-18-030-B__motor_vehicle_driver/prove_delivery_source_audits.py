"""Audit all current saved synthetic lane probe outputs independently."""

from __future__ import annotations

from hashlib import sha256
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
from time import time_ns


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def digest(path):
    return sha256(Path(path).read_bytes()).hexdigest()


def main():
    proof = json.loads((HERE / "delivery-saved-proofs.json").read_text())
    rows = []
    for row in proof["cases"]:
        words = shlex.split(row["command"])
        version = Path(words[words.index("--output") + 1]) / "v0001"
        if digest(version / "processing.json") != row["receipt_sha256"]:
            raise ValueError("Saved delivery proof receipt changed")
        suffix = row["case_id"].rsplit("__", 1)[-1]
        output = ROOT / ".runtime-work" / ("c147331-delivery-source-audit-" + suffix + "-" + str(time_ns()) + ".json")
        command = [sys.executable, str(HERE / "delivery_audit.py"),
                   "--attempt", str(version / "analysis"),
                   "--analysis", str(version / "analysis/analysis-report.json"),
                   "--output", str(output)]
        env = dict(os.environ)
        env["PYTHONPATH"] = os.pathsep.join([str(ROOT / "runtime/scenario_pipeline"),
                                            env.get("PYTHONPATH", "")])
        log = HERE / ("delivery-" + suffix + "-source-audit-command.log")
        with log.open("w") as stream:
            subprocess.run(command, cwd=ROOT, env=env, stdout=stream,
                           stderr=subprocess.STDOUT, check=True)
        audit = json.loads(output.read_text())
        if (audit.get("case_id") != row["case_id"] or audit.get("measurement_recomputed") is not True
                or len(audit.get("camera_decodes", {})) != 4
                or audit.get("physical_visibility_claimed") is not False):
            raise ValueError("Source audit incomplete: " + suffix)
        receipt = HERE / ("delivery-" + suffix + "-source-audit.json")
        shutil.copyfile(output, receipt)
        rows.append({"case_id": row["case_id"], "command": " ".join(command),
                     "exit_code": 0, "log": log.name, "log_sha256": digest(log),
                     "receipt": receipt.name, "receipt_sha256": digest(receipt),
                     "auditor_sha256": digest(HERE / "delivery_audit.py")})
    (HERE / "delivery-source-audit-proofs.json").write_text(json.dumps({
        "format": "worker-lane-delivery-source-audit-proofs", "delivery_ready": False,
        "cases": rows}, indent=2) + "\n")


if __name__ == "__main__":
    main()
