"""Prove the exact seven-case spawn-clearance fallback as CPU diagnostics."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
MANIFEST = ROOT / "diagnostic-execution-manifest.json"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def prove(output_root, validator):
    output_root = Path(output_root).resolve()
    if REPO / ".runtime-work" not in output_root.parents or output_root.exists():
        raise ValueError("Use a fresh proof root beneath .runtime-work")
    output_root.mkdir(parents=True)
    manifest = json.loads(MANIFEST.read_text())
    for entry in manifest["cases"]:
        case_id = entry["case_id"]
        suffix = case_id.rsplit("__", 1)[-1]
        folder = ROOT if suffix == "precedence" else ROOT / "cases" / suffix
        candidate = entry["candidates"][0]
        if candidate["id"] != "fallback1":
            raise ValueError("Expected one exact fallback1")
        command = [sys.executable, str(REPO / "runtime.py"), "offline",
                   "--manifest", str(MANIFEST), "--case", case_id,
                   "--candidate", "fallback1", "--output", str(output_root / suffix / "offline")]
        subprocess.run(command, cwd=REPO, env=os.environ, check=True,
                       stdout=subprocess.DEVNULL, timeout=120)
        offline_log = folder / "fallback1-offline.log"
        shutil.copyfile(output_root / suffix / "offline" / "offline.log", offline_log)
        candidate["offline"] = {"command": " ".join(command), "exit_code": 0,
                                "construction_sha256": candidate["construction_sha256"],
                                "log": str(offline_log.relative_to(ROOT)),
                                "log_sha256": sha(offline_log)}
        command = [sys.executable, str(REPO / "runtime.py"), "compatibility",
                   "--manifest", str(MANIFEST), "--case", case_id,
                   "--candidate", "fallback1", "--output", str(output_root / suffix / "compatibility"),
                   "--library", str(REPO / "runtime" / "library"),
                   "--validator", str(Path(validator).resolve())]
        subprocess.run(command, cwd=REPO, env=os.environ, check=True,
                       stdout=subprocess.DEVNULL, timeout=600)
        source = output_root / suffix / "compatibility"
        for original, returned in (("compatibility.json", "fallback1-compatibility.json"),
                                   ("compatibility-analysis.log", "fallback1-compatibility-analysis.log"),
                                   ("negative-analysis.log", "fallback1-compatibility-negative.log")):
            shutil.copyfile(source / original, folder / returned)
        receipt = folder / "fallback1-compatibility.json"
        value = json.loads(receipt.read_text())
        if (value.get("passed") is not True or value.get("case_id") != case_id or
                value.get("candidate_id") != "fallback1" or
                value.get("construction_sha256") != candidate["construction_sha256"]):
            raise ValueError("Fallback compatibility identity mismatch: " + suffix)
        candidate["compatibility"] = {
            "receipt": str(receipt.relative_to(ROOT)), "sha256": sha(receipt),
            "log": str((folder / "fallback1-compatibility-analysis.log").relative_to(ROOT)),
            "negative_log": str((folder / "fallback1-compatibility-negative.log").relative_to(ROOT))}
        print(json.dumps({"case_id": case_id, "candidate_id": "fallback1",
                          "offline_passed": True, "compatibility_passed": True,
                          "diagnostic_only": True}), flush=True)
    MANIFEST.write_text(json.dumps(manifest, indent=2) + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-root", required=True)
    parser.add_argument("--validator", required=True)
    args = parser.parse_args()
    prove(args.output_root, args.validator)
