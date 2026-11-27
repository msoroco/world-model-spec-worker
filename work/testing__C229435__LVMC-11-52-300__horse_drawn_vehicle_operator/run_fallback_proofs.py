"""Prove the exact long-capture queue fallback, including missing-source failure."""
import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
ASSIGNMENT = ROOT.name
TEMP = REPO / ".runtime-work/c229435-fallback"
VALIDATOR = REPO / ".runtime-work/c229435-diagnostic/validator/.lake/build/bin/adapterCheck"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    TEMP.mkdir(parents=True, exist_ok=True)
    manifest_path = ROOT / "execution-manifest.json"
    manifest = json.loads(manifest_path.read_text())
    for entry in manifest["cases"]:
        suffix = entry["case_id"].rsplit("__", 1)[-1]
        fallback = entry["candidates"][0]
        offline_path = TEMP / ("offline-" + suffix + "-v2")
        if not offline_path.exists():
            command = [str(REPO / ".venv-cpu/bin/python"), str(REPO / "runtime.py"),
                       "offline", "--manifest", str(manifest_path), "--case", entry["case_id"],
                       "--candidate", "fallback1", "--output", str(offline_path),
                       "--python", str(REPO / ".venv-cpu/bin/python")]
            subprocess.run(command, cwd=REPO, env=os.environ, check=True,
                           stdout=subprocess.DEVNULL)
        log = ROOT / ("proof-offline-fallback1-" + suffix + ".log")
        log.write_text((offline_path / "offline.log").read_text().rstrip() + "\n")
        fallback["offline"] = {"exit_code": 0,
            "construction_sha256": fallback["construction_sha256"],
            "command": ".venv-cpu/bin/python runtime.py offline --manifest work/" + ASSIGNMENT
                       + "/execution-manifest.json --case " + entry["case_id"]
                       + " --candidate fallback1 --output .runtime-work/c229435-fallback/offline-"
                       + suffix + "-v2 --python $PWD/.venv-cpu/bin/python",
            "log": log.name, "log_sha256": sha(log)}
        compat_path = TEMP / ("compat-" + suffix + "-v2")
        if not compat_path.exists():
            command = [str(REPO / ".venv-cpu/bin/python"), str(REPO / "runtime.py"),
                       "compatibility", "--manifest", str(manifest_path), "--case", entry["case_id"],
                       "--candidate", "fallback1", "--output", str(compat_path),
                       "--library", str(REPO / "runtime/library"), "--validator", str(VALIDATOR)]
            subprocess.run(command, cwd=REPO, env=os.environ, check=True,
                           stdout=subprocess.DEVNULL)
        receipt = json.loads((compat_path / "compatibility.json").read_text())
        if receipt.get("passed") is not True or receipt.get("construction_sha256") != fallback["construction_sha256"]:
            raise ValueError("fallback compatibility differs: " + suffix)
        targets = {"compatibility.json": ROOT / ("compat-fallback1-" + suffix + "-receipt.json"),
                   "compatibility-analysis.log": ROOT / ("compat-fallback1-" + suffix + "-analysis.log"),
                   "negative-analysis.log": ROOT / ("compat-fallback1-" + suffix + "-negative.log")}
        for source, target in targets.items():
            shutil.copyfile(compat_path / source, target)
            if target.read_bytes().endswith(b"\n\n"):
                raise ValueError("fallback log has blank EOF: " + suffix)
        fallback["compatibility"] = {"receipt": targets["compatibility.json"].name,
                                    "sha256": sha(targets["compatibility.json"]),
                                    "log": targets["compatibility-analysis.log"].name,
                                    "negative_log": targets["negative-analysis.log"].name}
        print("fallback pass", suffix, flush=True)
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")


if __name__ == "__main__":
    main()
