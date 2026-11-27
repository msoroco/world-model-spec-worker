"""Record three measured CPU outcomes and Native closure per exact case."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

HERE=Path(__file__).resolve().parent
REPO=HERE.parents[1]
SCRATCH=REPO/".runtime-work/c238432"
KINDS=("complete_motion","incomplete_motion","missing_evidence")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def build():
    SCRATCH.mkdir(parents=True,exist_ok=True)
    manifest_path=HERE/"execution-manifest.json"
    manifest=json.loads(manifest_path.read_text())
    env=dict(os.environ,SCENARIO_PIPELINE_OUTPUT_ROOT=str(SCRATCH),TMPDIR=str(SCRATCH),
             PYTHONDONTWRITEBYTECODE="1")
    for entry in manifest["cases"]:
        suffix=entry["case_id"].split("__")[-1]
        folder=HERE/"cases"/suffix
        fixtures=[]
        lifecycle=None
        for kind in KINDS:
            result=folder/("physical-"+kind+".json")
            log=folder/("physical-"+kind+".log")
            command=[sys.executable,str(HERE/"physical_probe.py"),"--case",entry["case_id"],
                     "--kind",kind,"--output",str(result)]
            run=subprocess.run(command,cwd=REPO,env=env,text=True,
                               stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=120)
            if run.returncode:
                raise RuntimeError(run.stdout[-3000:])
            log.write_text(run.stdout.rstrip()+"\n")
            payload=json.loads(run.stdout)
            fixtures.append({"kind":kind,"command":" ".join(command),"exit_code":0,
                "log":str(log.relative_to(HERE)),"log_sha256":sha(log),
                "result":str(result.relative_to(HERE)),"result_sha256":sha(result)})
            if kind=="complete_motion":
                lifecycle={"events":payload["lifecycle"],"exit_code":0,
                    "log":str(log.relative_to(HERE)),"log_sha256":sha(log)}
            print(suffix,kind,payload["status"],flush=True)
        receipt=folder/"physical-preparation.json"
        receipt.write_text(json.dumps({"construction_sha256":entry["construction_sha256"],
            "fixtures":fixtures,"lifecycle":lifecycle,"diagnostic_fixture":True,
            "physical_acceptance_claimed":False},sort_keys=True,indent=2)+"\n")
        entry["physical_preparation"]={"receipt":str(receipt.relative_to(HERE)),
            "sha256":sha(receipt)}
    manifest_path.write_text(json.dumps(manifest,indent=2,allow_nan=False)+"\n")


if __name__=="__main__":
    build()
