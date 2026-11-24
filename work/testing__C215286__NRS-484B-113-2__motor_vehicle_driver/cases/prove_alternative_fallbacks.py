"""Prove four exact Tesla spawn fallbacks through offline and compatibility paths."""

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
LABELS = ("intersection-entry", "intersection-stop", "corner-entry", "corner-stop")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, indent=2) + "\n")


def run():
    manifest = json.loads(MANIFEST.read_text())
    entries = [row for row in manifest["cases"] if "crosswalk" not in row["case_id"]]
    if len(entries) != 4:
        raise ValueError("Four selected alternatives required")
    for label, entry in zip(LABELS, entries):
        case_id = entry["case_id"]
        candidate = entry["candidates"][0]
        offline_dir = REPO / ".runtime-work" / ("c215286-alt-" + label + "-fallback1-offline")
        offline_log = PACKAGE / "cases" / (label + "-fallback1-offline.log")
        offline_cmd = [sys.executable, str(REPO / "runtime.py"), "offline", "--manifest", str(MANIFEST),
                       "--case", case_id, "--candidate", "fallback1", "--output", str(offline_dir)]
        if not offline_dir.exists():
            with offline_log.open("w") as log:
                result = subprocess.run(offline_cmd, cwd=REPO, stdout=log, stderr=subprocess.STDOUT,
                                        timeout=180, check=False)
            if result.returncode:
                raise RuntimeError("Fallback offline proof failed: " + case_id)
        if not offline_log.is_file() or not offline_dir.is_dir():
            raise ValueError("Fallback offline proof missing: " + case_id)
        candidate["offline"] = {"command": " ".join(offline_cmd), "exit_code": 0,
                                "construction_sha256": candidate["construction_sha256"],
                                "log": "cases/" + offline_log.name, "log_sha256": sha(offline_log)}
        compat_dir = REPO / ".runtime-work" / ("c215286-alt-" + label + "-fallback1-compat")
        compat_cmd = [sys.executable, str(REPO / "runtime.py"), "compatibility", "--manifest", str(MANIFEST),
                      "--case", case_id, "--candidate", "fallback1", "--output", str(compat_dir),
                      "--library", str(REPO / "runtime/library"), "--validator", str(DECODER)]
        if not (compat_dir / "compatibility.json").is_file():
            with (REPO / ".runtime-work" / ("c215286-alt-" + label + "-fallback1-compat.log")).open("w") as log:
                result = subprocess.run(compat_cmd, cwd=REPO, stdout=log, stderr=subprocess.STDOUT,
                                        timeout=900, check=False)
            if result.returncode:
                raise RuntimeError("Fallback compatibility failed: " + case_id)
        source_receipt = compat_dir / "compatibility.json"
        proof = json.loads(source_receipt.read_text())
        if not (proof["passed"] and proof["case_id"] == case_id and proof["candidate_id"] == "fallback1"
                and proof["construction_sha256"] == candidate["construction_sha256"]):
            raise ValueError("Fallback compatibility identity differs: " + case_id)
        receipt = PACKAGE / "cases" / (label + "-fallback1-compatibility-receipt.json")
        log = PACKAGE / "cases" / (label + "-fallback1-compatibility-analysis.log")
        negative = PACKAGE / "cases" / (label + "-fallback1-negative-analysis.log")
        shutil.copy2(source_receipt, receipt)
        shutil.copy2(compat_dir / "compatibility-analysis.log", log)
        shutil.copy2(compat_dir / "negative-analysis.log", negative)
        candidate["compatibility"] = {"command": " ".join(compat_cmd), "receipt": "cases/" + receipt.name,
                                      "sha256": sha(receipt), "log": "cases/" + log.name,
                                      "negative_log": "cases/" + negative.name,
                                      "negative_log_sha256": sha(negative)}
        print(label, "fallback1 offline and compatibility passed", flush=True)
    write(MANIFEST, manifest)


if __name__ == "__main__":
    run()
