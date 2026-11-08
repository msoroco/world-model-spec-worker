"""Run and retain eight synthetic v1 package positives and negatives."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
PYTHON = ROOT/".venv-cpu/bin/python"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    env = dict(os.environ)
    env["PATH"] = str(ROOT/".runtime-work/linux_arm64")+os.pathsep+env.get("PATH", "")
    env["LD_LIBRARY_PATH"] = str(ROOT/".runtime-work/geos-wheel/shapely.libs")+os.pathsep+env.get("LD_LIBRARY_PATH", "")
    results = []
    for kind in ("mounted_obey", "mounted_turn"):
        for candidate in ("primary", "fallback1", "fallback2", "fallback3"):
            command = [str(PYTHON), str(HERE/"prove-package-v1.py"),
                       "--kind", kind, "--candidate", candidate]
            run = subprocess.run(command, cwd=ROOT, env=env, text=True,
                                 stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=600)
            if run.returncode:
                raise RuntimeError(kind+" "+candidate+" package failed: "+run.stdout)
            result = json.loads(run.stdout)
            scratch = Path(result["scratch"])
            folder = HERE/"draft-exact-candidates"/kind/candidate/"package-proof"
            folder.mkdir(exist_ok=True)
            retained = {}
            for relative, source in (
                ("compatibility.json", scratch/"positive/compatibility.json"),
                ("analysis-report.json", scratch/"positive/analysis-report.json"),
                ("result.json", scratch/"positive/result.json"),
                ("final-decode.json", scratch/"positive/final-decode.json"),
                ("negative.log", scratch/"negative-analysis.log"),
                ("rider-source-manifest.json", scratch/"source/rider-source-manifest.json"),
                ("authored-sign.json", scratch/"source/authored-sign.json"),
                ("road.xodr", scratch/"source/road.xodr"),
                ("rider_native_samples.jsonl", scratch/"source/rider_native_samples.jsonl"),
                ("native_samples.jsonl", scratch/"source/native_samples.jsonl"),
                ("video_frames.jsonl", scratch/"source/video_frames.jsonl")):
                target = folder/relative
                shutil.copyfile(source, target)
                retained[relative] = sha(target)
            for i in range(4):
                source = scratch/"positive"/f"source-{i}.json"
                target = folder/f"source-{i}.json"
                shutil.copyfile(source, target)
                retained[target.name] = sha(target)
            compact = {"case_id": result["case_id"], "candidate_id": candidate,
                       "kind": kind, "positive_passed": result["positive"]["passed"],
                       "negative_rejected": result["negative"]["rejected"],
                       "construction_sha256": result["positive"]["construction_sha256"],
                       "retained_sha256": retained, "scope": "unselected synthetic v1 software diagnostic",
                       "original_native_capture_executed": False, "selected": False}
            (folder/"durable-receipt.json").write_text(json.dumps(compact,indent=2,sort_keys=True)+"\n")
            results.append({"kind": kind, "candidate_id": candidate,
                            "receipt": (folder/"durable-receipt.json").relative_to(HERE).as_posix(),
                            "sha256": sha(folder/"durable-receipt.json")})
            print(kind,candidate,"positive and negative passed",flush=True)
    index = {"format": "c104538-lvmc-synthetic-package-index-v1", "results": results,
             "positive_count": len(results), "negative_count": len(results),
             "original_native_capture_executed": False, "selected": False}
    (HERE/"draft-package-durable-index.json").write_text(json.dumps(index,indent=2,sort_keys=True)+"\n")


if __name__ == "__main__":
    main()
