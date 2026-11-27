"""Run case-bound positive and missing-source compatibility through pinned runtime."""
import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
ASSIGNMENT = ROOT.name
RUNTIME_WORK = REPO / ".runtime-work/c229435-diagnostic"
VALIDATOR = RUNTIME_WORK / "validator/.lake/build/bin/adapterCheck"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    if not VALIDATOR.is_file():
        raise ValueError("pinned decoder must be built before compatibility")
    path = ROOT / "execution-manifest.json"
    manifest = json.loads(path.read_text())
    for entry in manifest["cases"]:
        suffix = entry["case_id"].rsplit("__", 1)[-1]
        attempt = RUNTIME_WORK / ("compat-" + suffix + "-v6")
        if not attempt.exists():
            command = [str(REPO / ".venv-cpu/bin/python"), str(REPO / "runtime.py"),
                       "compatibility", "--manifest", str(path), "--case", entry["case_id"],
                       "--output", str(attempt), "--library", str(REPO / "runtime/library"),
                       "--validator", str(VALIDATOR)]
            subprocess.run(command, cwd=REPO, env=os.environ, check=True,
                           stdout=subprocess.DEVNULL)
        receipt = json.loads((attempt / "compatibility.json").read_text())
        if receipt.get("passed") is not True or receipt.get("construction_sha256") != entry["construction_sha256"]:
            raise ValueError("compatibility receipt differs: " + suffix)
        targets = {
            "compatibility.json": ROOT / ("compat-" + suffix + "-receipt.json"),
            "compatibility-analysis.log": ROOT / ("compat-" + suffix + "-analysis.log"),
            "negative-analysis.log": ROOT / ("compat-" + suffix + "-negative.log"),
        }
        for source, target in targets.items():
            shutil.copyfile(attempt / source, target)
            if target.read_bytes().endswith(b"\n\n"):
                raise ValueError("retained compatibility log has blank EOF: " + suffix)
        entry["compatibility"] = {"receipt": targets["compatibility.json"].name,
                                  "sha256": sha(targets["compatibility.json"]),
                                  "log": targets["compatibility-analysis.log"].name,
                                  "negative_log": targets["negative-analysis.log"].name}
        entry["negative"] = {"log": targets["negative-analysis.log"].name}
        print("compatibility pass", suffix, flush=True)
    path.write_text(json.dumps(manifest, indent=2) + "\n")


if __name__ == "__main__":
    main()
