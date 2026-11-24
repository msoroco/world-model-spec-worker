"""Exercise saved-only processing for every exact C158208-2 CPU diagnostic.

This builds fresh diagnostic acquisitions under .runtime-work. It never starts
Native CARLA and never claims that fixture motion establishes legal or physical
acceptance.
"""

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
sys.dont_write_bytecode = True
from check_source_fixture import ensure_validator

ROOT = Path(__file__).resolve().parents[2]
PACKAGE = Path(__file__).resolve().parent
MANIFEST = PACKAGE / "probe-manifest.json"
OUTPUT_ROOT = ROOT / ".runtime-work"
VALIDATOR = OUTPUT_ROOT / "c158208-current-validator/.lake/build/bin/adapterCheck"


def read(path):
    return json.loads(path.read_text())


def source_hashes(folder):
    return {str(path.relative_to(folder)): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in sorted(folder.rglob("*")) if path.is_file()}


def run(*args):
    environment = dict(os.environ, PYTHONDONTWRITEBYTECODE="1",
                       SCENARIO_PIPELINE_OUTPUT_ROOT=str(OUTPUT_ROOT / "c158208-post-capture"))
    command = [str(ROOT / ".venv-cpu/bin/python"), str(ROOT / "runtime.py"), *map(str, args)]
    result = subprocess.run(command, cwd=ROOT, env=environment, text=True,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    if result.returncode:
        raise ValueError("Runtime command failed: " + " ".join(command[2:])
                         + "\n" + result.stdout[-2000:])
    return result.stdout


def one(entry, temporary, manifest):
    case = entry["case_id"]
    kind = case.split("__")[-1]
    materialized = temporary / (kind + "-materialized")
    fixture = temporary / (kind + "-fixture")
    positive = temporary / (kind + "-positive")
    negative = temporary / (kind + "-negative")
    negative_output = temporary / (kind + "-negative-output")
    run("materialize", "--manifest", manifest, "--case", case, "--output", materialized)
    run("fixture", "--recipe", ROOT / entry["fixture_recipe"], "--output", fixture)
    for path in fixture.iterdir():
        target = materialized / path.name
        if target.exists():
            raise ValueError("Diagnostic source shadows selected implementation: " + path.name)
        if path.is_dir():
            shutil.copytree(path, target)
        else:
            shutil.copy2(path, target)
    before = source_hashes(materialized)
    base = ("--manifest", manifest, "--case", case,
            "--library", ROOT / "runtime/library", "--validator", VALIDATOR)
    run("process-saved", *base, "--attempt", materialized, "--output", positive)
    receipt = read(positive / "v0001/processing.json")
    if (receipt.get("case_id") != case or receipt.get("passed") is not True
            or receipt.get("recorded_only") is not True
            or receipt.get("missing_evidence") is not False
            or receipt.get("originals_preserved") is not True
            or receipt.get("physical_acceptance_claimed") is not False
            or receipt.get("legal_acceptance_claimed") is not False
            or receipt.get("timestamp_joins", {}).get("passed") is not True
            or receipt.get("final_video_checks", {}).get("passed") is not True):
        raise ValueError("Incomplete positive saved-only processing: " + case)
    if source_hashes(materialized) != before:
        raise ValueError("Saved-only processing changed original diagnostic acquisition")
    shutil.copytree(materialized, negative)
    contract = read(PACKAGE / entry["measurement_contract"])
    missing_source = contract["negative"]["remove"][0]
    (negative / missing_source).unlink()
    negative_before = source_hashes(negative)
    run("process-saved", *base, "--attempt", negative, "--output", negative_output)
    rejected = read(negative_output / "v0001/processing.json")
    feedback = read(negative_output / "v0001/feedback.json")
    if (rejected.get("missing_evidence") is not True
            or rejected.get("originals_preserved") is not True
            or feedback.get("recorded_only") is not True
            or feedback.get("native_replay_requested") is not False
            or contract["negative"]["error_contains"] not in feedback.get("error", "")):
        raise ValueError("Missing-source feedback failed: " + case)
    if source_hashes(negative) != negative_before:
        raise ValueError("Negative saved-only processing changed diagnostic acquisition")
    return {"case_id": case, "positive_saved_processing": True,
            "negative_missing_source": missing_source, "recorded_only": True,
            "originals_preserved": True, "final_decoded_frames": receipt["final_video_checks"]["frames"],
            "physical_acceptance_claimed": False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--case")
    parser.add_argument("--manifest", type=Path, default=MANIFEST)
    args = parser.parse_args()
    ensure_validator()
    manifest = read(args.manifest)
    entries = [e for e in manifest["cases"] if not args.case or e["case_id"] == args.case]
    if not entries or (args.case and len(entries) != 1):
        raise ValueError("Select an exact case")
    OUTPUT_ROOT.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(dir=OUTPUT_ROOT, prefix="c158208-saved-fixtures-") as name:
        output = [one(entry, Path(name), args.manifest) for entry in entries]
    print(json.dumps({"format": "c158208-post-capture-cpu-check", "cases": output}, sort_keys=True))


if __name__ == "__main__":
    main()
