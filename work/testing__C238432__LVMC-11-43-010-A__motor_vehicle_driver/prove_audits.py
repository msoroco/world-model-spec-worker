"""Record independent delivery and controlled-direction comparison proofs."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

HERE=Path(__file__).resolve().parent
REPO=HERE.parents[1]
SCRATCH=REPO/".runtime-work/c238432"
CHECKS=["native_source","all_participants","time_join","full_video_decode",
        "actual_pixels","physical_completion"]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def call(command):
    env=dict(os.environ,SCENARIO_PIPELINE_OUTPUT_ROOT=str(SCRATCH),TMPDIR=str(SCRATCH),
             PYTHONDONTWRITEBYTECODE="1")
    return subprocess.run(command,cwd=REPO,env=env,text=True,
                          stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=600)


def prove():
    manifest_path=HERE/"execution-manifest.json"
    manifest=json.loads(manifest_path.read_text())
    stamp=str(time.time_ns())
    attempts={}
    for entry in manifest["cases"]:
        suffix=entry["case_id"].split("__")[-1]
        folder=HERE/"cases"/suffix
        tokens=entry["compatibility"]["command"].split()
        attempt=Path(tokens[tokens.index("--output")+1])
        attempts[suffix]=attempt
        output=SCRATCH/("independent-audit-"+suffix+"-"+stamp+".json")
        command=[sys.executable,str(HERE/"delivery_audit.py"),"--case-id",entry["case_id"],
            "--attempt",str(attempt),"--plan",str(HERE/"case-plan.json"),"--output",str(output)]
        positive=call(command)
        if positive.returncode:
            raise RuntimeError(positive.stdout[-2500:])
        audit=json.loads(output.read_text())
        if audit["case_id"]!=entry["case_id"] or not audit["source_video_join"] or len(audit["four_view_full_decode"])!=4:
            raise ValueError("independent positive audit incomplete")
        log=folder/"delivery-positive.log"
        log.write_text(json.dumps(audit,sort_keys=True,indent=2)+"\n")
        missing=SCRATCH/("audit-missing-"+suffix+"-"+stamp)
        shutil.copytree(attempt,missing)
        (missing/"history.json").unlink()
        negative_command=command.copy()
        negative_command[negative_command.index("--attempt")+1]=str(missing)
        negative_command[negative_command.index("--output")+1]=str(SCRATCH/("audit-missing-output-"+suffix+"-"+stamp+".json"))
        negative=call(negative_command)
        expected="Missing required source: history.json"
        if negative.returncode==0 or expected not in negative.stdout:
            raise ValueError("independent missing original history not rejected")
        negative_log=folder/"delivery-negative.log"
        negative_log.write_text(negative.stdout.rstrip()+"\n")
        entry["delivery_acceptance"]={"case_id":entry["case_id"],"sets":["full-test"],
            "checks":CHECKS,"script":"delivery_audit.py","script_sha256":sha(HERE/"delivery_audit.py"),
            "command":" ".join(command),"test_exit_code":0,
            "test_log":str(log.relative_to(HERE)),"test_log_sha256":sha(log),
            "negative_command":" ".join(negative_command),
            "negative_exit_code":negative.returncode,"negative_expected_error":expected,
            "negative_log":str(negative_log.relative_to(HERE)),
            "negative_log_sha256":sha(negative_log)}
        print("independent delivery positive and negative passed",suffix,flush=True)
    output=SCRATCH/("comparison-audit-"+stamp+".json")
    command=[sys.executable,str(HERE/"comparison_audit.py"),
        "--counterclockwise",str(attempts["counterclockwise"]),
        "--clockwise",str(attempts["clockwise"]),
        "--comparison-id",HERE.name+"__roundabout_circulation_direction",
        "--plan",str(HERE/"case-plan.json"),"--output",str(output)]
    positive=call(command)
    if positive.returncode:raise RuntimeError(positive.stdout[-2500:])
    compared=json.loads(output.read_text())
    if compared["measured"]["observed_directions"]!=["counterclockwise","clockwise"]:
        raise ValueError("comparison observation changed")
    comparison_log=HERE/"comparison-positive.log"
    comparison_log.write_text(json.dumps(compared,sort_keys=True,indent=2)+"\n")
    missing=SCRATCH/("comparison-missing-"+stamp)
    shutil.copytree(attempts["clockwise"],missing)
    (missing/"map.json").unlink()
    negative_command=command.copy()
    negative_command[negative_command.index("--clockwise")+1]=str(missing)
    negative_command[negative_command.index("--output")+1]=str(SCRATCH/("comparison-missing-output-"+stamp+".json"))
    negative=call(negative_command)
    expected="Missing required source: map.json"
    if negative.returncode==0 or expected not in negative.stdout:
        raise ValueError("comparison missing original map not rejected")
    negative_log=HERE/"comparison-negative.log"
    negative_log.write_text(negative.stdout.rstrip()+"\n")
    manifest["comparison_audit"]={"comparison_id":"roundabout_circulation_direction",
        "script":"comparison_audit.py","script_sha256":sha(HERE/"comparison_audit.py"),
        "command":" ".join(command),"exit_code":0,
        "log":comparison_log.name,"log_sha256":sha(comparison_log),
        "negative_command":" ".join(negative_command),"negative_exit_code":negative.returncode,
        "negative_expected_error":expected,"negative_log":negative_log.name,
        "negative_log_sha256":sha(negative_log)}
    manifest_path.write_text(json.dumps(manifest,indent=2,allow_nan=False)+"\n")
    print("independent comparison positive and negative passed",flush=True)


if __name__=="__main__":
    prove()
