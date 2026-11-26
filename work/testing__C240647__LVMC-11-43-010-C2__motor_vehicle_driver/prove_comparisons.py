"""Prove eight exact controlled comparisons and fixed-source rejection."""
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
SCRATCH=REPO/".runtime-work/c240647-owner-final/comparison-proofs"

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def write(path,value):
    path.write_text(json.dumps(value,sort_keys=True,indent=2)+"\n")

def prove():
    plan=json.loads((HERE/"case-plan.json").read_text())
    SCRATCH.mkdir(parents=True,exist_ok=True)
    env=os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"]="1"
    for comparison in plan["comparisons"]:
        cid=comparison["comparison_id"]
        left,right=comparison["case_ids"]
        left_name=left.removeprefix(HERE.name+"__")
        right_name=right.removeprefix(HERE.name+"__")
        first=REPO/".runtime-work/c240647-owner-final"/("compat-final-"+left_name+"-primary")
        second=REPO/".runtime-work/c240647-owner-final"/("compat-final-"+right_name+"-primary")
        positive=SCRATCH/(cid+"-positive.json")
        if positive.exists():
            positive.unlink()
        cmd=[str(PYTHON),str(HERE/"comparison_audit.py"),"--first",str(first),
             "--second",str(second),"--comparison",cid,"--comparison-id",HERE.name+"__"+cid,
             "--plan",str(HERE/"case-plan.json"),"--output",str(positive)]
        result=subprocess.run(cmd,cwd=REPO,env=env,capture_output=True,text=True)
        log=HERE/("cpu-comparison-"+cid+".log")
        log.write_text((result.stdout+result.stderr).rstrip()+"\n" if result.stdout or result.stderr else
                       positive.read_text().rstrip()+"\n" if positive.is_file() else "failure\n")
        if result.returncode or not positive.is_file():
            raise RuntimeError("comparison positive failed: "+cid+" "+result.stderr[-1000:])
        if json.loads(positive.read_text())["case_ids"]!=comparison["case_ids"]:
            raise ValueError("comparison output scope mismatch")
        damaged=SCRATCH/(cid+"-damaged")
        if damaged.exists():
            shutil.rmtree(damaged)
        shutil.copytree(second,damaged)
        history=damaged/"history.json"
        packet=json.loads(history.read_text())
        packet["weather_sha256"]="0"*64
        write(history,packet)
        inventory=damaged/"inventory.json"
        refs=json.loads(inventory.read_text())
        refs["sources"]["history"]["sha256"]=sha(history)
        write(inventory,refs)
        negative=SCRATCH/(cid+"-negative.json")
        if negative.exists():
            negative.unlink()
        ncmd=cmd.copy()
        ncmd[ncmd.index("--second")+1]=str(damaged)
        ncmd[ncmd.index("--output")+1]=str(negative)
        failed=subprocess.run(ncmd,cwd=REPO,env=env,capture_output=True,text=True)
        nlog=HERE/("cpu-comparison-"+cid+"-negative.log")
        nlog.write_text((failed.stdout+failed.stderr).rstrip()+"\n")
        if failed.returncode==0 or "comparison fixed source changed" not in nlog.read_text():
            raise ValueError("comparison fixed-source negative failed: "+cid)
        receipt={"format":"worker-independent-comparison-proof","assignment_id":HERE.name,
                 "comparison_id":cid,"case_ids":comparison["case_ids"],
                 "command":" ".join(cmd),"exit_code":0,"log":log.name,"log_sha256":sha(log),
                 "negative_command":" ".join(ncmd),"negative_exit_code":failed.returncode,
                 "negative_error":"comparison fixed source changed","negative_log":nlog.name,
                 "negative_log_sha256":sha(nlog),"physical_acceptance_claimed":False}
        write(HERE/("comparison-"+cid+"-receipt.json"),receipt)
        print("comparison",cid,"passed",flush=True)

if __name__=="__main__":
    prove()
