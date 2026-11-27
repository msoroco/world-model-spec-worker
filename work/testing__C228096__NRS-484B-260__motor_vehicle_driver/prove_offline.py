"""Run exact primary and fallback offline checks in scratch and retain receipts."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys


ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
MANIFEST = ROOT / "execution-manifest.draft.json"


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    scratch = Path(os.environ["SCENARIO_PIPELINE_OUTPUT_ROOT"]).resolve()
    if ".runtime-work" not in scratch.parts:
        raise ValueError("offline scratch must be under .runtime-work")
    scratch.mkdir(parents=True, exist_ok=True)
    manifest = json.loads(MANIFEST.read_text())
    for entry in manifest["cases"]:
        variant = entry["case_id"].split("__")[-1]
        for candidate in ("primary", "fallback1"):
            attempt = scratch / (variant + "-" + candidate)
            if attempt.exists():
                shutil.rmtree(attempt)
            command = [sys.executable, str(REPO / "runtime.py"), "offline",
                       "--manifest", str(MANIFEST), "--case", entry["case_id"],
                       "--output", str(attempt), "--python", sys.executable,
                       "--candidate", candidate]
            result = subprocess.run(command, cwd=REPO, capture_output=True, text=True)
            if result.returncode:
                raise ValueError("offline check failed for " + variant + " " +
                                 candidate + ": " + result.stderr[-1000:])
            proof = ROOT / "cases" / variant / ("proof-offline-" + candidate + ".log")
            content = (attempt / "offline.log").read_text().rstrip() + "\n"
            proof.write_text(content)
            receipt = {"exit_code": 0, "command": " ".join(command),
                       "log": str(proof.relative_to(ROOT)),
                       "log_sha256": _sha(proof),
                       "construction_sha256": entry["construction_sha256"] if candidate == "primary"
                           else entry["candidates"][0]["construction_sha256"]}
            if candidate == "primary":
                entry["offline"] = receipt
            else:
                entry["candidates"][0]["offline"] = receipt
    MANIFEST.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    print(len(manifest["cases"]) * 2)


if __name__ == "__main__":
    main()
