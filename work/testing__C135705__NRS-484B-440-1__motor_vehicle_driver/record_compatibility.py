"""Retain all six pinned positive/negative compatibility receipts and hashes."""
from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
VALIDATOR=ROOT/".runtime-work/c109755-decoder-v2/.lake/build/bin/adapterCheck"


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    path=HERE/"execution-manifest.json";manifest=json.loads(path.read_text())
    proof_root=(ROOT/(HERE/"compat-proof-root.txt").read_text().strip()).resolve()
    for entry in manifest["cases"]:
        suffix=entry["case_id"].removeprefix(HERE.name+"__")
        folder=HERE/"cases"/suffix
        for candidate in ("primary","fallback1"):
            selected=entry if candidate=="primary" else entry["candidates"][0]
            output=proof_root/suffix/candidate
            receipt=json.loads((output/"compatibility.json").read_text())
            if receipt.get("passed") is not True or receipt.get("case_id")!=entry["case_id"] or receipt.get("candidate_id")!=candidate:
                raise ValueError("exact compatibility proof absent")
            if receipt.get("construction_sha256")!=selected["construction_sha256"]:
                raise ValueError("compatibility proof construction changed")
            names={"compatibility.json":candidate+"-compatibility.json",
                   "compatibility-analysis.log":candidate+"-compat-analysis.log",
                   "negative-analysis.log":candidate+"-compat-negative.log"}
            for old,new in names.items():shutil.copyfile(output/old,folder/new)
            relative=lambda name:f"cases/{suffix}/{name}"
            command=(f"{ROOT}/.venv-cpu/bin/python {ROOT}/runtime.py compatibility "
                f"--manifest {path} --case {entry['case_id']} --candidate {candidate} "
                f"--output {output} --library {ROOT/'runtime/library'} --validator {VALIDATOR}")
            selected["compatibility"]={"receipt":relative(names["compatibility.json"]),
                "sha256":sha(folder/names["compatibility.json"]),
                "log":relative(names["compatibility-analysis.log"]),
                "negative_log":relative(names["negative-analysis.log"]),
                "command":command,"exit_code":0,
                "command_log":relative(candidate+"-compat-command.log"),
                "command_log_sha256":sha(folder/(candidate+"-compat-command.log"))}
            if candidate=="primary":
                entry["negative"]={"log":relative(names["negative-analysis.log"]),
                                   "sha256":sha(folder/names["negative-analysis.log"])}
        entry["proof_status"]="offline_and_positive_negative_compatibility_passed_delivery_audit_pending"
    manifest["status"]="compatibility_passed_delivery_audit_pending"
    path.write_text(json.dumps(manifest,indent=2,allow_nan=False)+"\n")
    print("six pinned compatibility receipts retained, including missing-source negatives")


if __name__=="__main__":main()
