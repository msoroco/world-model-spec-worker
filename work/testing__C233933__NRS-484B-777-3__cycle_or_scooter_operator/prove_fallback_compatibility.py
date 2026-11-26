"""Run selected measurement, negative source, Core and decode checks on fallbacks."""

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
MANIFEST = HERE / "execution-manifest.selected-draft.json"
SCRATCH = ROOT / ".runtime-work" / "c233933-owner-nov26" / "rider-formation-fallback-compat-c233933-v3"
VALIDATOR = ROOT / ".runtime-work" / "c110969-decoder" / ".lake" / "build" / "bin" / "adapterCheck"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run():
    SCRATCH.mkdir(parents=True, exist_ok=True)
    if not VALIDATOR.is_file():
        raise ValueError("pinned Lean validator missing")
    manifest = json.loads(MANIFEST.read_text())
    for entry in manifest["cases"]:
        suffix = entry["case_id"].removeprefix(HERE.name + "__")
        candidate = entry["candidates"][0]
        if candidate["id"] != "fallback1":
            raise ValueError("expected exact fallback")
        destination = SCRATCH / suffix
        if destination.exists():
            raise ValueError("retain previous fallback compatibility proof")
        command = [sys.executable, str(ROOT / "runtime.py"), "compatibility",
                   "--manifest", str(MANIFEST), "--case", entry["case_id"],
                   "--candidate", "fallback1", "--output", str(destination),
                   "--library", str(ROOT / "runtime" / "library"),
                   "--validator", str(VALIDATOR)]
        env = dict(os.environ, SCENARIO_PIPELINE_OUTPUT_ROOT=str(SCRATCH), TMPDIR=str(SCRATCH))
        result = subprocess.run(command, cwd=ROOT, env=env, text=True,
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        command_log = HERE / ("proof-fallback-command-" + suffix + ".log")
        command_log.write_text(result.stdout.rstrip() + "\n")
        if result.returncode:
            raise ValueError("fallback compatibility failed: " + entry["case_id"])
        receipt = json.loads((destination / "compatibility.json").read_text())
        if (receipt.get("passed") is not True or receipt.get("case_id") != entry["case_id"] or
                receipt.get("candidate_id") != "fallback1" or
                receipt.get("construction_sha256") != candidate["construction_sha256"]):
            raise ValueError("fallback compatibility receipt incomplete")
        for source, target in (("compatibility.json", "proof-fallback-receipt-" + suffix + ".json"),
                               ("compatibility-analysis.log", "proof-fallback-analysis-" + suffix + ".log"),
                               ("negative-analysis.log", "proof-fallback-negative-" + suffix + ".log")):
            (HERE / target).write_text(((destination / source).read_text().rstrip() + "\n" if (destination / source).read_text().strip() else ""))
        receipt_path = HERE / ("proof-fallback-receipt-" + suffix + ".json")
        candidate["compatibility"] = {
            "receipt": receipt_path.name, "sha256": sha(receipt_path),
            "log": "proof-fallback-analysis-" + suffix + ".log",
            "negative_log": "proof-fallback-negative-" + suffix + ".log"}
    MANIFEST.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")
    return len(manifest["cases"])


if __name__ == "__main__":
    print("fallback compatibility proofs:", run())
