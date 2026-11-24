"""Run the pinned CPU compatibility proof for each exact diagnostic case."""
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

OWN = Path(__file__).resolve().parent
REPO = OWN.parents[1]
MANIFEST = OWN / "execution-manifest.json"
VALIDATOR = REPO / ".runtime-work/c10307-decoder/.lake/build/bin/adapterCheck"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    manifest = json.loads(MANIFEST.read_text())
    for entry in manifest["cases"]:
        case_id = entry["case_id"]
        short = case_id.removeprefix(manifest["assignment_id"] + "__")
        output = REPO / (".runtime-work/c10307-compat-native-v12-" + short)
        command = [str(REPO / ".venv-cpu/bin/python"), str(REPO / "runtime.py"), "compatibility",
                   "--manifest", str(MANIFEST), "--case", case_id, "--output", str(output),
                   "--library", str(REPO / "runtime/library"), "--validator", str(VALIDATOR)]
        log = OWN / ("cpu-compat-" + short + ".log")
        with log.open("w") as stream:
            completed = subprocess.run(command, cwd=REPO, env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"),
                                       stdout=stream, stderr=subprocess.STDOUT, timeout=300)
        print(short, completed.returncode, sha(log), flush=True)
        if completed.returncode:
            continue
        for source, destination in (("compatibility.json", "cpu-compatibility-" + short + ".json"),
                                    ("compatibility-analysis.log", "cpu-compat-analysis-" + short + ".log"),
                                    ("negative-analysis.log", "cpu-negative-analysis-" + short + ".log")):
            (OWN / destination).write_bytes((output / source).read_bytes())
        entry["compatibility"] = {"receipt": "cpu-compatibility-" + short + ".json",
                                   "sha256": sha(OWN / ("cpu-compatibility-" + short + ".json")),
                                   "log": "cpu-compat-analysis-" + short + ".log"}
        entry["negative"] = {"log": "cpu-negative-analysis-" + short + ".log"}
    MANIFEST.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main()
