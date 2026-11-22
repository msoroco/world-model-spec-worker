"""Reject altered OpenDRIVE bytes in each materialized exact-case bundle."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path


HERE=Path(__file__).resolve().parent
REPO=HERE.parents[1]
ATTEMPTS=REPO/".runtime-work/c126120-offline-current"


def main():
    manifest=json.loads((HERE/"execution-manifest.json").read_text())
    checked=[]
    for entry in manifest["cases"]:
        suffix=entry["case_id"].rsplit("__",1)[-1]
        source=ATTEMPTS/suffix
        if not (source/"offline.log").is_file():
            raise ValueError("exact offline positive proof absent: "+suffix)
        with tempfile.TemporaryDirectory(dir=REPO/".runtime-work",
                                         prefix="c126120-negative-") as temp:
            target=Path(temp)/"bundle"
            shutil.copytree(source,target)
            map_path=target/"road.xodr"
            map_path.write_bytes(map_path.read_bytes()+b" ")
            env=dict(os.environ,PYTHONDONTWRITEBYTECODE="1")
            run=subprocess.run([str(REPO/".venv-cpu/bin/python"),"runner.py","--check"],
                               cwd=target,env=env,text=True,
                               stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=60)
            expected="authored OpenDRIVE source hash differs from scene"
            if run.returncode==0 or expected not in run.stdout:
                raise AssertionError("changed exact-case map accepted: "+suffix+"\n"+run.stdout)
            log=HERE/"cases"/suffix/"negative-offline.log"
            log.write_text(run.stdout)
            checked.append(suffix)
    print(json.dumps({"negative_changed_map_rejected":checked,
                      "delivery_ready_claimed":False}))


if __name__=="__main__":main()
