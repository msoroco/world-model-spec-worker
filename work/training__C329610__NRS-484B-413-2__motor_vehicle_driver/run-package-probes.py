"""Run 24 exact unselected v1 synthetic portable probes."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent


def main():
    env = dict(os.environ)
    env["PATH"] = str(REPO / ".runtime-work/linux_arm64") + os.pathsep + env.get("PATH", "")
    env["LD_LIBRARY_PATH"] = str(REPO / ".runtime-work/geos-wheel/shapely.libs") + os.pathsep + env.get("LD_LIBRARY_PATH", "")
    manifest = json.loads((HERE / "draft-execution-manifest.json").read_text())
    records = []
    for entry in manifest["cases"]:
        suffix = entry["case_id"].split("__")[-1]
        for candidate in ("primary", "fallback1", "fallback2", "fallback3"):
            log = HERE / ("package-v1-" + suffix + "-" + candidate + ".log")
            command = [str(REPO / ".venv-cpu/bin/python"), str(HERE / "probe-package-compatibility.py"),
                       "--suffix", suffix, "--candidate", candidate]
            with log.open("w") as stream:
                run = subprocess.run(command, cwd=REPO, env=env, stdout=stream,
                                     stderr=subprocess.STDOUT, timeout=900)
            print(suffix, candidate, "exit", run.returncode, flush=True)
            if run.returncode:
                print(log.read_text()[-1800:], file=sys.stderr)
                raise SystemExit(run.returncode)
            result = json.loads(log.read_text().splitlines()[-1])
            assert result["positive"]["passed"] and result["negative"]["exit_code"] != 0
            records.append({"case_id":entry["case_id"],"candidate_id":candidate,
                "construction_sha256":result["positive"]["construction_sha256"],
                "log":str(log.relative_to(HERE)),"log_sha256":hashlib.sha256(log.read_bytes()).hexdigest(),
                "positive_format":result["positive"]["format"],"negative_removed":result["negative"]["removed"],
                "selected":False,"synthetic":True})
    (HERE / "draft-package-probe-summary.json").write_text(json.dumps({
        "format":"c329610-413-2-v1-synthetic-package-matrix-v1", "results":records,
        "selected":False,"original_native_observed":False},indent=2)+"\n")


if __name__ == "__main__":
    main()
