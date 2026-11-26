"""Bind per-case physical-state and Native lifecycle CPU fixture receipts."""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import subprocess

HERE=Path(__file__).resolve().parent
REPO=HERE.parents[1]
PYTHON=REPO/".venv-cpu/bin/python"
MANIFEST=HERE/"execution-manifest.json"

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def write(path,value):
    path.write_text(json.dumps(value,sort_keys=True,indent=2)+"\n")

def prove():
    manifest=json.loads(MANIFEST.read_text())
    env=os.environ.copy()
    env["SCENARIO_PIPELINE_OUTPUT_ROOT"]=str(REPO/".runtime-work/c240647-owner/output")
    env["PYTHONDONTWRITEBYTECODE"]="1"
    for entry in manifest["cases"]:
        case=entry["case_id"]
        name=case.removeprefix(HERE.name+"__")
        fixtures=[]
        for kind,expected in (("complete_motion","met"),("incomplete_motion","not_met"),
                              ("missing_evidence","unverified")):
            target=HERE/f"physical-{name}-{kind}.json"
            log=HERE/f"physical-{name}-{kind}.log"
            command=[str(PYTHON),str(HERE/"physical_probe.py"),"--case",case,"--kind",kind,
                     "--output",str(target)]
            result=subprocess.run(command,cwd=REPO,env=env,capture_output=True,text=True)
            log.write_text((result.stdout+result.stderr).rstrip()+"\n")
            if result.returncode:
                raise RuntimeError(f"physical {name} {kind}: "+result.stderr[-1200:])
            value=json.loads(target.read_text())
            if value["physical_checks"]["maneuver"]["status"]!=expected or value["physical_acceptance_claimed"]:
                raise ValueError("physical fixture outcome or provenance differs")
            fixtures.append({"kind":kind,"command":" ".join(command),"exit_code":0,
                 "result":target.name,"result_sha256":sha(target),"log":log.name,"log_sha256":sha(log)})
        complete=fixtures[0]
        result=json.loads((HERE/complete["log"]).read_text())
        receipt={"format":"worker-physical-preparation","case_id":case,
                 "construction_sha256":entry["construction_sha256"],"fixtures":fixtures,
                 "lifecycle":{"command":complete["command"],"exit_code":0,
                              "events":result["lifecycle"],"log":complete["log"],
                              "log_sha256":complete["log_sha256"]},
                 "scope":"synthetic CPU protocol only; no physical acceptance"}
        path=HERE/f"physical-{name}-receipt.json"
        write(path,receipt)
        entry["physical_preparation"]={"receipt":path.name,"sha256":sha(path)}
        print("physical+lifecycle",name,"passed",flush=True)
    write(MANIFEST,manifest)

if __name__=="__main__":
    prove()
