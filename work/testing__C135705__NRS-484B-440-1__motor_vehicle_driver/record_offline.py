"""Attach exact successful offline receipt hashes to the draft manifest."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    proof_root=(ROOT/(HERE/"construction-proof-root.txt").read_text().strip()).resolve()
    manifest_path=HERE/"execution-manifest.json"
    manifest=json.loads(manifest_path.read_text())
    for entry in manifest["cases"]:
        suffix=entry["case_id"].removeprefix(HERE.name+"__")
        for candidate in ("primary","fallback1"):
            selected=entry if candidate=="primary" else entry["candidates"][0]
            log=HERE/"cases"/suffix/(candidate+"-offline.log")
            output=proof_root/suffix/candidate
            report=json.loads(log.read_text())
            if report.get("offline_passed") is not True or report.get("case_id")!=entry["case_id"] or report.get("candidate_id")!=candidate:
                raise ValueError("exact offline proof did not pass")
            if not (output/"offline.log").is_file():raise ValueError("runtime offline log absent")
            command=(f"{ROOT}/.venv-cpu/bin/python {ROOT}/runtime.py offline "
                f"--manifest {manifest_path} --case {entry['case_id']} --candidate {candidate} "
                f"--output {output} --python {ROOT}/.venv-cpu/bin/python")
            selected["offline"]={"command":command,"exit_code":0,
                "construction_sha256":selected["construction_sha256"],
                "log":f"cases/{suffix}/{candidate}-offline.log","log_sha256":sha(log),
                "runtime_offline_log_sha256":sha(output/"offline.log")}
        entry["proof_status"]="primary_and_fallback_offline_passed_compatibility_pending"
    manifest["status"]="offline_passed_compatibility_pending"
    manifest_path.write_text(json.dumps(manifest,indent=2,allow_nan=False)+"\n")
    print("six exact offline receipts attached")


if __name__=="__main__":main()
