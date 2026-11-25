"""Bind current exact-construction offline CPU proof logs."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def bind():
    path = HERE / "execution-manifest.json"
    manifest = json.loads(path.read_text())
    for entry in manifest["cases"]:
        case = entry["case_id"]
        suffix = case.rsplit("__", 1)[-1]
        log = HERE / ("proof-offline-" + suffix + ".log")
        result = json.loads((HERE / ("proof-offline-" + suffix + "-result.json")).read_text())
        if (result.get("case_id") != case or result.get("offline_passed") is not True or
                "OK" not in log.read_text()):
            raise ValueError("offline proof incomplete: " + case)
        entry["offline"] = {"command": f".venv-cpu/bin/python runtime.py offline --manifest {path} --case {case} --output $SCRATCH --python .venv-cpu/bin/python",
                            "exit_code": 0, "construction_sha256": entry["construction_sha256"],
                            "log": log.name, "log_sha256": sha(log)}
    path.write_text(json.dumps(manifest, indent=2) + "\n")
    print("bound", len(manifest["cases"]), "exact offline proofs")


if __name__ == "__main__":
    bind()
