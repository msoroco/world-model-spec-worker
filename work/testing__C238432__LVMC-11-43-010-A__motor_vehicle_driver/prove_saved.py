"""Exercise recorded-only processing and missing original direction history."""

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
VALIDATOR=REPO/".runtime-work/c110969-decoder/.lake/build/bin/adapterCheck"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def invoke(command):
    env=dict(os.environ, SCENARIO_PIPELINE_OUTPUT_ROOT=str(SCRATCH),
             TMPDIR=str(SCRATCH), PYTHONDONTWRITEBYTECODE="1")
    completed=subprocess.run(command,cwd=REPO,env=env,text=True,
                             stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=600)
    if completed.returncode:
        raise RuntimeError(completed.stdout[-3000:])
    return json.loads(completed.stdout)


def prove():
    manifest_path=HERE/"execution-manifest.json"
    manifest=json.loads(manifest_path.read_text())
    stamp=str(time.time_ns())
    for entry in manifest["cases"]:
        suffix=entry["case_id"].split("__")[-1]
        folder=HERE/"cases"/suffix
        source=entry["compatibility"]["command"].split()
        original=Path(source[source.index("--output")+1])
        attempt=SCRATCH/("saved-attempt-"+suffix+"-"+stamp)
        shutil.copytree(original,attempt)
        selection=attempt/"candidate-selection.json"
        if selection.exists():selection.unlink()
        output=SCRATCH/("saved-output-"+suffix+"-"+stamp)
        command=[sys.executable,str(REPO/"runtime.py"),"process-saved",
                 "--manifest",str(manifest_path),"--case",entry["case_id"],
                 "--attempt",str(attempt),"--output",str(output),
                 "--library",str(REPO/"runtime/library"),"--validator",str(VALIDATOR)]
        positive=invoke(command)
        if not (positive.get("passed") and positive.get("originals_preserved") and
                positive.get("timestamp_joins",{}).get("passed") and
                not positive.get("missing_evidence")):
            raise ValueError("saved positive did not preserve originals and joins: "+suffix)
        positive_log=folder/"proof-saved-positive.log"
        positive_log.write_text(json.dumps(positive,sort_keys=True,indent=2)+"\n")
        missing=SCRATCH/("saved-missing-attempt-"+suffix+"-"+stamp)
        shutil.copytree(attempt,missing)
        (missing/"history.json").unlink()
        negative_output=SCRATCH/("saved-missing-output-"+suffix+"-"+stamp)
        feedback=command.copy()
        feedback[feedback.index("--attempt")+1]=str(missing)
        feedback[feedback.index("--output")+1]=str(negative_output)
        negative=invoke(feedback)
        if not negative.get("missing_evidence") or "history.json" not in (negative_output/"v0001/feedback.json").read_text():
            raise ValueError("missing original direction history was not rejected: "+suffix)
        negative_log=folder/"proof-saved-negative.log"
        negative_log.write_text(json.dumps(negative,sort_keys=True,indent=2)+"\n")
        entry["post_capture"]={"command":" ".join(command),"feedback_command":" ".join(feedback),
            "test_log":str(positive_log.relative_to(HERE)),"test_log_sha256":sha(positive_log),
            "test_exit_code":0,"feedback_log":str(negative_log.relative_to(HERE)),
            "feedback_log_sha256":sha(negative_log),"feedback_test_exit_code":0,
            "recorded_only":True,"diagnostic_fixture":True,"physical_acceptance_claimed":False}
        print("saved positive and missing source negative passed",suffix,flush=True)
    manifest_path.write_text(json.dumps(manifest,indent=2,allow_nan=False)+"\n")


if __name__=="__main__":
    prove()
