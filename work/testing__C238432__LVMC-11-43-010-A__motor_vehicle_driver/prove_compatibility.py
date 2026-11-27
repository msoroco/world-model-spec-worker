"""Run exact primary/fallback offline and positive/negative CPU compatibility."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

HERE=Path(__file__).resolve().parent
REPO=HERE.parents[1]
SCRATCH=REPO/".runtime-work/c238432"
VALIDATOR=REPO/".runtime-work/c110969-decoder/.lake/build/bin/adapterCheck"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def run(args):
    env=dict(os.environ)
    env["SCENARIO_PIPELINE_OUTPUT_ROOT"]=str(SCRATCH)
    env["TMPDIR"]=str(SCRATCH)
    env["PYTHONDONTWRITEBYTECODE"]="1"
    env["MPLCONFIGDIR"]=str(SCRATCH/"matplotlib")
    result=subprocess.run(args,cwd=REPO,env=env,text=True,
                          stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=600)
    if result.returncode:
        raise RuntimeError("CPU command failed: "+" ".join(map(str,args))+"\n"+result.stdout[-2500:])
    return result.stdout


def build():
    SCRATCH.mkdir(parents=True,exist_ok=True)
    manifest_path=HERE/"execution-manifest.json"
    manifest=json.loads(manifest_path.read_text())
    marker=str(int(time.time()*1000000))
    for entry in manifest["cases"]:
        suffix=entry["case_id"].split("__")[-1]
        folder=HERE/"cases"/suffix
        for candidate in ("primary","fallback1"):
            target=entry if candidate=="primary" else entry["candidates"][0]
            offline_dir=SCRATCH/("offline-"+suffix+"-"+candidate+"-"+marker)
            args=[sys.executable,str(REPO/"runtime.py"),"offline",
                "--manifest",str(manifest_path),"--case",entry["case_id"],
                "--output",str(offline_dir),"--python",sys.executable]
            if candidate!="primary":args.extend(["--candidate",candidate])
            run(args)
            offline_log=folder/("proof-offline-"+candidate+".log")
            shutil.copyfile(offline_dir/"offline.log",offline_log)
            target["offline"]={"command":" ".join(args),"exit_code":0,
                "log":str(offline_log.relative_to(HERE)),"log_sha256":sha(offline_log),
                "construction_sha256":target["construction_sha256"]}
            compat_dir=SCRATCH/("compat-"+suffix+"-"+candidate+"-"+marker)
            args=[sys.executable,str(REPO/"runtime.py"),"compatibility",
                "--manifest",str(manifest_path),"--case",entry["case_id"],
                "--output",str(compat_dir),"--library",str(REPO/"runtime/library"),
                "--validator",str(VALIDATOR)]
            if candidate!="primary":args.extend(["--candidate",candidate])
            run(args)
            receipt=folder/("proof-compat-"+candidate+".json")
            analysis=folder/("proof-compat-"+candidate+"-analysis.log")
            negative=folder/("proof-compat-"+candidate+"-negative.log")
            shutil.copyfile(compat_dir/"compatibility.json",receipt)
            shutil.copyfile(compat_dir/"compatibility-analysis.log",analysis)
            shutil.copyfile(compat_dir/"negative-analysis.log",negative)
            target["compatibility"]={"command":" ".join(args),
                "receipt":str(receipt.relative_to(HERE)),"sha256":sha(receipt),
                "log":str(analysis.relative_to(HERE)),
                "negative_log":str(negative.relative_to(HERE)),
                "negative_log_sha256":sha(negative)}
            if candidate=="primary":
                entry["negative"]={"log":str(negative.relative_to(HERE)),
                                   "log_sha256":sha(negative)}
            print(suffix,candidate,"offline and compatibility passed",flush=True)
    manifest_path.write_text(json.dumps(manifest,indent=2,allow_nan=False)+"\n")


if __name__=="__main__":
    build()
