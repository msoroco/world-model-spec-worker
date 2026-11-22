"""Reject a changed authored OpenDRIVE source in every exact primary bundle."""
from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    manifest_path=HERE/"execution-manifest.json";manifest=json.loads(manifest_path.read_text())
    proof_root=(ROOT/(HERE/"construction-proof-root.txt").read_text().strip()).resolve()
    for entry in manifest["cases"]:
        suffix=entry["case_id"].removeprefix(HERE.name+"__")
        source=proof_root/suffix/"primary"
        with tempfile.TemporaryDirectory(dir=ROOT/".runtime-work",prefix="c135705-negative-road-") as temp:
            destination=Path(temp)/"bundle"
            shutil.copytree(source,destination)
            road=destination/"road.xodr"
            road.write_text(road.read_text().replace('name="C135705 standing geometry candidate"',
                                                     'name="tampered candidate"',1))
            result=subprocess.run([sys.executable,str(destination/"runner.py"),"--check"],
                cwd=destination,capture_output=True,text=True)
            if result.returncode==0 or "OpenDRIVE source hash differs" not in result.stderr:
                raise AssertionError("tampered road source was not rejected: "+suffix)
            log=HERE/"cases"/suffix/"negative-offline.log"
            log.write_text(result.stdout+result.stderr)
        entry["offline_negative"]={"command":
            f"{ROOT}/.venv-cpu/bin/python {HERE}/prove_offline_negative.py",
            "expected_error":"OpenDRIVE source hash differs","log":f"cases/{suffix}/negative-offline.log",
            "log_sha256":sha(log),"nonzero_exit_verified":True}
        print(suffix,"tampered road rejected")
    manifest_path.write_text(json.dumps(manifest,indent=2,allow_nan=False)+"\n")


if __name__=="__main__":main()
