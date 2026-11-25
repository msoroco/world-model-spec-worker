"""Bind current six exact positive/negative diagnostic compatibility receipts."""
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
        receipt_path = HERE / ("compat-" + suffix + "-receipt.json")
        log = HERE / ("compat-" + suffix + "-analysis.log")
        negative = HERE / ("compat-" + suffix + "-negative.log")
        proof = json.loads(receipt_path.read_text())
        if (proof.get("passed") is not True or proof.get("case_id") != case or
                proof.get("construction_sha256") != entry["construction_sha256"] or
                proof.get("log_sha256") != sha(log) or
                proof.get("negative_log_sha256") != sha(negative) or
                proof.get("negative_error_contains") not in negative.read_text()):
            raise ValueError("compatibility proof stale or incomplete: " + case)
        entry["compatibility"] = {
            "command": f".venv-cpu/bin/python runtime.py compatibility --manifest {path} --case {case} --output $SCRATCH --library runtime/library --validator $VALIDATOR",
            "receipt": receipt_path.name, "sha256": sha(receipt_path),
            "log": log.name, "negative_log": negative.name}
        entry["negative"] = {"log": negative.name,
                             "log_sha256": sha(negative)}
    path.write_text(json.dumps(manifest, indent=2) + "\n")
    print("bound", len(manifest["cases"]), "exact compatibility receipts")


if __name__ == "__main__":
    bind()
