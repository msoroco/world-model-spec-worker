"""Run all 24 exact unselected v1 synthetic package positive/negative probes."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

HERE=Path(__file__).resolve().parent
ROOT=HERE.parent.parent

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def main():
    env=dict(os.environ)
    env["PATH"]=str(ROOT/".runtime-work/linux_arm64")+os.pathsep+env.get("PATH","")
    env["LD_LIBRARY_PATH"]=str(ROOT/".runtime-work/geos-wheel/shapely.libs")+os.pathsep+env.get("LD_LIBRARY_PATH","")
    records=[]
    for feet in (90,100,110,290,300,310):
        for candidate in ("primary","fallback1","fallback2","fallback3"):
            cmd=[sys.executable,str(HERE/"probe-package-compatibility.py"),
                 "--feet",str(feet),"--candidate",candidate]
            result=subprocess.run(cmd,cwd=ROOT,env=env,stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,text=True,timeout=300)
            log=HERE/f"package-probe-{feet}-{candidate}.log"
            log.write_text(result.stdout)
            if result.returncode:
                raise RuntimeError(f"{feet} {candidate}: {result.stdout[-1500:]}")
            receipt=HERE/f"package-probe-{feet}-{candidate}.json"
            payload=json.loads(receipt.read_text())
            assert payload["positive"]["passed"] is True
            assert payload["negative_exit_code"]!=0 and payload["synthetic"] is True
            records.append({"feet":feet,"candidate_id":candidate,"receipt":receipt.name,
                "receipt_sha256":sha(receipt),"log":log.name,"log_sha256":sha(log),
                "construction_sha256":payload["positive"]["construction_sha256"]})
            print(feet,candidate,"positive and negative pass",flush=True)
    summary={"format":"c104393-unselected-package-diagnostics-v1",
        "passed":True,"cases":6,"candidates":24,"positive":24,"negative":24,
        "synthetic":True,"selected":False,"physical_success_claimed":False,
        "records":records}
    (HERE/"package-probes-summary.json").write_text(json.dumps(summary,indent=2)+"\n")

if __name__=="__main__":main()
