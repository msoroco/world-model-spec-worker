"""Exercise pinned saved-only postprocessing on diagnostic original sources."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]


def digest(root):
    return {str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in root.rglob("*") if path.is_file()}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--negative", action="store_true")
    args = parser.parse_args()
    manifest_path = HERE/"execution-manifest.json"
    manifest = json.loads(manifest_path.read_text())
    entry = next(item for item in manifest["cases"] if item["case_id"] == args.case)
    tokens = shlex.split(entry["compatibility"]["command"])
    source = (REPO/tokens[tokens.index("--output")+1]).resolve()
    output = Path(args.output).resolve()
    source_copy = output.with_name(output.name+"-source")
    if (not source.is_relative_to(REPO/".runtime-work") or
            not output.is_relative_to(REPO/".runtime-work") or
            output.exists() or source_copy.exists()):
        raise ValueError("fresh saved-processing probe under .runtime-work required")
    shutil.copytree(source, source_copy)
    (source_copy/"candidate-selection.json").unlink()
    if args.negative:
        (source_copy/"walker-body-history.jsonl").unlink()
    before = digest(source_copy)
    command = [sys.executable, str(REPO/"runtime.py"), "process-saved",
               "--manifest", str(manifest_path), "--case", args.case,
               "--attempt", str(source_copy), "--output", str(output),
               "--library", str(REPO/"runtime/library"),
               "--validator", str(REPO/".runtime-work/c109755-decoder-v2/.lake/build/bin/adapterCheck")]
    env = dict(os.environ)
    env["SCENARIO_PIPELINE_OUTPUT_ROOT"] = str(REPO/".runtime-work/c143766-saved-probe-runtime")
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    completed = subprocess.run(command, cwd=REPO, env=env, capture_output=True,
                               text=True, timeout=300)
    if completed.returncode:
        raise RuntimeError("Pinned saved processing failed: "+completed.stderr[-1200:])
    receipt = json.loads((output/"v0001/processing.json").read_text())
    if (digest(source_copy) != before or receipt.get("passed") is not True or
            receipt.get("originals_preserved") is not True or
            receipt.get("missing_evidence") is not args.negative or
            receipt.get("physical_acceptance_claimed") is not False):
        raise AssertionError("saved-only processing or missing-source feedback differs")
    if not args.negative and not receipt.get("final_video_checks", {}).get("passed"):
        raise AssertionError("positive saved-only final video proof missing")
    print(json.dumps({"case_id": args.case, "recorded_only": True,
                      "missing_evidence": receipt["missing_evidence"],
                      "originals_preserved": True,
                      "final_video_decoded": bool(receipt.get("final_video_checks", {}).get("passed")),
                      "physical_acceptance_claimed": False}, indent=2))


if __name__ == "__main__":
    main()
