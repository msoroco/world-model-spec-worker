"""Rebind selected exact offline and compatibility proofs to the refreshed runtime."""

import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path


REPO = Path(__file__).resolve().parents[3]
PACKAGE = Path(__file__).resolve().parents[1]
MANIFEST = PACKAGE / "execution-manifest.json"
DECODER = REPO / ".runtime-work/c215286-current-decoder/.lake/build/bin/adapterCheck"
RUNTIME_SHA = hashlib.sha256((REPO / "runtime/SOURCE-MANIFEST.json").read_bytes()).hexdigest()


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, indent=2) + "\n")


def run():
    manifest = json.loads(MANIFEST.read_text())
    if manifest["runtime_manifest_sha256"] != RUNTIME_SHA or len(manifest["cases"]) != 6:
        raise ValueError("Select all six cases on the refreshed runtime first")
    for entry in manifest["cases"]:
        suffix = entry["case_id"].split("__")[-1]
        for selected in [entry, *entry.get("candidates", [])]:
            candidate_id = selected.get("id", "primary")
            label = suffix + "-" + candidate_id
            construction = PACKAGE / selected["construction"]
            if sha(construction) != selected["construction_sha256"]:
                raise ValueError("Changed construction: " + label)
            output = REPO / ".runtime-work/c215286-current-runtime-reproof" / suffix / candidate_id
            offline = output / "offline"
            compat = output / "compatibility"
            offline_log = PACKAGE / "cases" / (label + "-current-runtime-offline.log")
            offline_cmd = [sys.executable, str(REPO / "runtime.py"), "offline",
                           "--manifest", str(MANIFEST), "--case", entry["case_id"],
                           "--candidate", candidate_id, "--output", str(offline)]
            if not (offline / "offline.log").is_file():
                offline.parent.mkdir(parents=True, exist_ok=True)
                with offline_log.open("w") as log:
                    result = subprocess.run(offline_cmd, cwd=REPO, stdout=log,
                                            stderr=subprocess.STDOUT, timeout=180, check=False)
                if result.returncode:
                    raise RuntimeError("Current-runtime offline failed: " + label)
            elif not offline_log.is_file():
                shutil.copy2(offline / "offline.log", offline_log)
            selected["offline"] = {"command": " ".join(offline_cmd), "exit_code": 0,
                                   "construction_sha256": selected["construction_sha256"],
                                   "log": "cases/" + offline_log.name, "log_sha256": sha(offline_log)}
            compat_cmd = [sys.executable, str(REPO / "runtime.py"), "compatibility",
                          "--manifest", str(MANIFEST), "--case", entry["case_id"],
                          "--candidate", candidate_id, "--output", str(compat),
                          "--library", str(REPO / "runtime/library"), "--validator", str(DECODER)]
            if not (compat / "compatibility.json").is_file():
                compat.parent.mkdir(parents=True, exist_ok=True)
                with (output / "compatibility-command.log").open("w") as log:
                    result = subprocess.run(compat_cmd, cwd=REPO, stdout=log,
                                            stderr=subprocess.STDOUT, timeout=900, check=False)
                if result.returncode:
                    raise RuntimeError("Current-runtime compatibility failed: " + label)
            proof = json.loads((compat / "compatibility.json").read_text())
            if not (proof["passed"] and proof["case_id"] == entry["case_id"]
                    and proof["candidate_id"] == candidate_id
                    and proof["construction_sha256"] == selected["construction_sha256"]
                    and proof["runtime_manifest_sha256"] == RUNTIME_SHA):
                raise ValueError("Current-runtime compatibility identity differs: " + label)
            receipt = PACKAGE / "cases" / (label + "-current-runtime-compatibility-receipt.json")
            log = PACKAGE / "cases" / (label + "-current-runtime-compatibility-analysis.log")
            negative = PACKAGE / "cases" / (label + "-current-runtime-negative-analysis.log")
            shutil.copy2(compat / "compatibility.json", receipt)
            shutil.copy2(compat / "compatibility-analysis.log", log)
            shutil.copy2(compat / "negative-analysis.log", negative)
            selected["compatibility"] = {"command": " ".join(compat_cmd),
                                         "receipt": "cases/" + receipt.name, "sha256": sha(receipt),
                                         "log": "cases/" + log.name, "negative_log": "cases/" + negative.name,
                                         "negative_log_sha256": sha(negative)}
            if candidate_id == "primary":
                entry["negative"] = {"log": "cases/" + negative.name, "sha256": sha(negative)}
            write(MANIFEST, manifest)
            print(label, "current-runtime offline and compatibility passed", flush=True)


if __name__ == "__main__":
    run()
