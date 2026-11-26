"""Prove nine independent original-source/full-decode delivery audits."""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess

HERE=Path(__file__).resolve().parent
REPO=HERE.parents[1]
PYTHON=REPO/".venv-cpu/bin/python"
SCRATCH=REPO/".runtime-work/c240647-owner-final/delivery-proofs"
MANIFEST=HERE/"execution-manifest.json"
CHECKS=["native_source","all_participants","time_join","full_video_decode","actual_pixels","physical_completion"]

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def run(command,env):
    return subprocess.run(command,cwd=REPO,env=env,capture_output=True,text=True)

def prove():
    manifest=json.loads(MANIFEST.read_text())
    SCRATCH.mkdir(parents=True,exist_ok=True)
    env=os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"]="1"
    for entry in manifest["cases"]:
        case=entry["case_id"]
        name=case.removeprefix(HERE.name+"__")
        attempt=REPO/".runtime-work/c240647-owner-final"/("compat-final-"+name+"-primary")
        positive=SCRATCH/(name+"-audit.json")
        if positive.exists():
            positive.unlink()
        command=[str(PYTHON),str(HERE/"delivery_audit.py"),"--case-id",case,
                 "--attempt",str(attempt),"--plan",str(HERE/"case-plan.json"),"--output",str(positive)]
        result=run(command,env)
        log=HERE/("cpu-delivery-"+name+".log")
        log.write_text((result.stdout+result.stderr).rstrip()+"\n" if result.stdout or result.stderr else
                       json.dumps(json.loads(positive.read_text()),sort_keys=True)+"\n" if positive.is_file() else "failure\n")
        if result.returncode or not positive.is_file():
            raise RuntimeError("delivery positive failed: "+name+" "+result.stderr[-1000:])
        proof=json.loads(positive.read_text())
        if (proof["case_id"]!=case or proof["capture_frames"]!=9 or proof["packet_frames"]!=9
                or len(proof["four_view_full_decode"])!=4 or not proof["diagnostic_fixture"]):
            raise ValueError("delivery audit incomplete: "+name)
        missing=SCRATCH/(name+"-missing")
        if missing.exists():
            shutil.rmtree(missing)
        shutil.copytree(attempt,missing)
        (missing/"history.json").unlink()
        negative=SCRATCH/(name+"-negative.json")
        if negative.exists():
            negative.unlink()
        ncmd=command.copy()
        ncmd[ncmd.index("--attempt")+1]=str(missing)
        ncmd[ncmd.index("--output")+1]=str(negative)
        failed=run(ncmd,env)
        nlog=HERE/("cpu-delivery-"+name+"-negative.log")
        nlog.write_text((failed.stdout+failed.stderr).rstrip()+"\n")
        if failed.returncode==0 or "Missing required source: history.json" not in nlog.read_text():
            raise ValueError("delivery negative did not reject missing original history: "+name)
        entry["delivery_acceptance"]={"case_id":case,"sets":["full-test"],"checks":CHECKS,
            "command":" ".join(command),"negative_command":" ".join(ncmd),
            "script":"delivery_audit.py","script_sha256":sha(HERE/"delivery_audit.py"),
            "test_exit_code":0,"test_log":log.name,"test_log_sha256":sha(log),
            "negative_exit_code":failed.returncode,"negative_expected_error":"Missing required source: history.json",
            "negative_log":nlog.name,"negative_log_sha256":sha(nlog),
            "diagnostic_fixture":True,"physical_acceptance_claimed":False}
        print("delivery audit",name,"passed",flush=True)
    MANIFEST.write_text(json.dumps(manifest,sort_keys=True,indent=2)+"\n")

if __name__=="__main__":
    prove()
