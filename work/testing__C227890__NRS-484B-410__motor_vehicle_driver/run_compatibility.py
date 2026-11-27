"""Run and bind exact positive/negative pinned runtime compatibility proofs."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
MANIFEST = ROOT / "execution-manifest.json"
VALIDATOR = REPO / ".runtime-work/c109755-decoder-v2/.lake/build/bin/adapterCheck"


def _sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _clean(source, target):
    raw = source.read_text()
    clean = "\n".join(line.rstrip() for line in raw.splitlines()).rstrip()
    target.write_text(clean + "\n" if clean else "")


def run():
    scratch = Path(os.environ["SCENARIO_PIPELINE_OUTPUT_ROOT"]).resolve()
    if ".runtime-work" not in scratch.parts or not VALIDATOR.is_file():
        raise ValueError("pinned compatibility scratch or validator missing")
    scratch.mkdir(parents=True, exist_ok=True)
    manifest = json.loads(MANIFEST.read_text())
    python = Path(sys.executable)
    for entry in manifest["cases"]:
        variant = entry["case_id"].removeprefix(manifest["assignment_id"] + "__")
        for candidate, target in ((None, entry), ("fallback1", entry["candidates"][0])):
            label = variant + ("-fallback1" if candidate else "-primary")
            destination = scratch / ("compat-" + label)
            if destination.exists():
                raise ValueError("refusing to replace compatibility proof " + label)
            command = [str(python), str(REPO / "runtime.py"), "compatibility",
                       "--manifest", str(MANIFEST), "--case", entry["case_id"],
                       "--output", str(destination), "--library", str(REPO / "runtime/library"),
                       "--validator", str(VALIDATOR)]
            if candidate:
                command += ["--candidate", candidate]
            process = subprocess.run(command, cwd=REPO, capture_output=True, text=True,
                                     timeout=300, env=os.environ.copy())
            if process.returncode:
                raise ValueError("compatibility proof failed " + label + ": " + process.stderr[-1000:])
            receipt = json.loads((destination / "compatibility.json").read_text())
            if (receipt.get("case_id") != entry["case_id"] or
                    receipt.get("candidate_id") != (candidate or "primary") or
                    receipt.get("passed") is not True or
                    receipt.get("construction_sha256") != target["construction_sha256"]):
                raise ValueError("compatibility receipt identity or result differs: " + label)
            analysis = ROOT / ("cpu-compat-" + label + "-analysis.log")
            negative = ROOT / ("cpu-compat-" + label + "-negative.log")
            receipt_path = ROOT / ("cpu-compat-" + label + "-receipt.json")
            _clean(destination / "compatibility-analysis.log", analysis)
            _clean(destination / "negative-analysis.log", negative)
            if "Missing required source: original-attempt/activity.jsonl" not in negative.read_text():
                raise ValueError("missing-source negative did not fail as expected: " + label)
            receipt_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
            target["compatibility"] = {"command": " ".join(command),
                                       "receipt": receipt_path.name,
                                       "sha256": _sha(receipt_path),
                                       "log": analysis.name,
                                       "negative_log": negative.name,
                                       "negative_log_sha256": _sha(negative)}
            if candidate is None:
                entry["negative"] = {"log": negative.name,
                                     "log_sha256": _sha(negative)}
    MANIFEST.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    return len(manifest["cases"]) * 2


if __name__ == "__main__":
    print(run())
