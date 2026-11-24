"""Exercise pinned saved-only processing on exact synthetic case sources."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile


ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
RUNTIME = REPO / ".runtime-work"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(*args):
    command = [str(REPO / ".venv-cpu/bin/python"), str(REPO / "runtime.py"), *map(str, args)]
    completed = subprocess.run(command, cwd=REPO, env=os.environ, capture_output=True, text=True)
    if completed.returncode:
        raise RuntimeError("pinned saved command failed: " + completed.stdout[-1200:] + completed.stderr[-1200:])
    return json.loads(completed.stdout)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", required=True)
    parser.add_argument("--candidate", choices=("primary", "fallback1"), default="primary")
    args = parser.parse_args()
    output_root = Path(os.environ["SCENARIO_PIPELINE_OUTPUT_ROOT"]).resolve()
    if not output_root.is_relative_to(RUNTIME.resolve()):
        raise ValueError("pipeline output root must be under .runtime-work")
    manifest_path = ROOT / "execution-manifest.json"
    manifest = json.loads(manifest_path.read_text())
    entry = next((row for row in manifest["cases"] if row["case_id"] == args.case), None)
    if entry is None:
        raise ValueError("select exact case")
    with tempfile.TemporaryDirectory(dir=RUNTIME, prefix="c147332-12a-saved-") as temporary:
        base = Path(temporary)
        fixture, attempt, output = base / "fixture", base / "attempt", base / "processed"
        run("fixture", "--recipe", REPO / entry["fixture_recipe"], "--output", fixture)
        run("materialize", "--manifest", manifest_path, "--case", args.case,
            "--candidate", args.candidate, "--output", attempt)
        for source in fixture.iterdir():
            target = attempt / source.name
            if target.exists():
                raise ValueError("fixture shadows package")
            if source.is_dir():
                shutil.copytree(source, target)
            else:
                shutil.copy2(source, target)
        before = {str(p.relative_to(attempt)): digest(p) for p in attempt.rglob("*") if p.is_file()}
        receipt = run("process-saved", "--manifest", manifest_path, "--case", args.case,
                      "--attempt", attempt, "--output", output,
                      "--library", REPO / "runtime/library",
                      "--validator", RUNTIME / "c109755-decoder-v2/.lake/build/bin/adapterCheck")
        after = {str(p.relative_to(attempt)): digest(p) for p in attempt.rglob("*") if p.is_file()}
        if before != after or receipt.get("recorded_only") is not True or receipt.get("passed") is not True:
            raise AssertionError("saved processing modified originals or failed")
        if receipt.get("missing_evidence") is not False or receipt.get("physical_acceptance_claimed") is not False:
            raise AssertionError("saved processing result exceeded diagnostic scope")
        if receipt.get("candidate_id") != args.candidate or receipt.get("case_id") != args.case:
            raise AssertionError("saved processing selected another case or candidate")
        negative_attempt = base / "missing-signal-attempt"
        shutil.copytree(attempt, negative_attempt)
        (negative_attempt / "lane-signal-history.jsonl").unlink()
        negative_before = {str(p.relative_to(negative_attempt)): digest(p)
                           for p in negative_attempt.rglob("*") if p.is_file()}
        rejected = run("process-saved", "--manifest", manifest_path, "--case", args.case,
                       "--attempt", negative_attempt, "--output", base / "missing-signal-output",
                       "--library", REPO / "runtime/library",
                       "--validator", RUNTIME / "c109755-decoder-v2/.lake/build/bin/adapterCheck")
        negative_after = {str(p.relative_to(negative_attempt)): digest(p)
                          for p in negative_attempt.rglob("*") if p.is_file()}
        if negative_before != negative_after or rejected.get("missing_evidence") is not True:
            raise AssertionError("missing original signal was accepted or negative original changed")
        feedback = json.loads((base / "missing-signal-output/v0001/feedback.json").read_text())
        if feedback.get("native_replay_requested") is not False or feedback.get("recorded_only") is not True:
            raise AssertionError("missing signal requested Native replay")
        print(args.case, args.candidate,
              "pinned saved-only positive and missing-signal negative passed; originals preserved; synthetic source only")


if __name__ == "__main__":
    main()
