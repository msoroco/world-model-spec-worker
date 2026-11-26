"""Exercise exact selected draft saved processing on case-shaped CPU sources."""

import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess


HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
SUFFIXES = ("witness_1", "witness_2", "exception_1_1", "exception_1_2")


def run(command, log, env):
    with log.open("w") as handle:
        completed = subprocess.run(command, cwd=REPO, env=env, stdout=handle,
                                   stderr=subprocess.STDOUT, check=False)
    if completed.returncode:
        raise RuntimeError(f"Command failed ({completed.returncode}): {log}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--scratch", type=Path, required=True)
    parser.add_argument("--validator", type=Path, required=True)
    args = parser.parse_args()
    scratch = args.scratch.resolve()
    if REPO / ".runtime-work" not in scratch.parents:
        raise ValueError("Scratch must be under .runtime-work")
    scratch.mkdir(parents=True, exist_ok=True)
    validator = args.validator.resolve()
    if not validator.is_file():
        raise ValueError("Current decoder is absent")
    env = os.environ.copy()
    env.update(TMPDIR=str(scratch), SCENARIO_PIPELINE_OUTPUT_ROOT=str(scratch),
               PYTHONDONTWRITEBYTECODE="1")
    manifest = HERE / "selected-native-draft-manifest.json"
    for suffix in SUFFIXES:
        case = HERE.name + "__" + suffix
        attempt = scratch / ("attempt-" + suffix)
        source = REPO / ".runtime-work" / ("c247014-compat-" + suffix + "-v4")
        public = json.loads((source / "compatibility.json").read_text())
        if public.get("case_id") != case or public.get("passed") is not True:
            raise ValueError("Public compatibility source not exact: " + suffix)
        run([str(REPO / ".venv-cpu/bin/python"), "-B", "runtime.py", "materialize",
             "--manifest", str(manifest), "--case", case, "--output", str(attempt)],
            scratch / ("materialize-" + suffix + ".log"), env)
        for relative in public["fixture_manifest"]:
            source_file = source / relative
            target = attempt / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source_file, target)
        run([str(REPO / ".venv-cpu/bin/python"), "-B", "runtime.py", "process-saved",
             "--manifest", str(manifest), "--case", case, "--attempt", str(attempt),
             "--output", str(scratch / ("saved-" + suffix)),
             "--library", "runtime/library", "--validator", str(validator)],
            scratch / ("saved-" + suffix + ".log"), env)
        print(suffix + ": saved positive passed", flush=True)
    negative = scratch / "attempt-witness_1-negative"
    shutil.copytree(scratch / "attempt-witness_1", negative)
    (negative / "pass-context.json").unlink()
    command = [str(REPO / ".venv-cpu/bin/python"), "-B", "runtime.py", "process-saved",
               "--manifest", str(manifest), "--case", HERE.name + "__witness_1",
               "--attempt", str(negative), "--output", str(scratch / "saved-witness_1-negative"),
               "--library", "runtime/library", "--validator", str(validator)]
    run(command, scratch / "saved-witness_1-negative.log", env)
    versions = sorted((scratch / "saved-witness_1-negative").glob("v*/processing.json"))
    if len(versions) != 1:
        raise ValueError("Negative saved result missing")
    receipt = json.loads(versions[0].read_text())
    feedback = json.loads((versions[0].parent / "feedback.json").read_text())
    if (receipt.get("missing_evidence") is not True or
            feedback.get("classification") != "incomplete_or_unavailable_law_evidence" or
            "Missing required source: pass-context.json" not in feedback.get("error", "") or
            receipt.get("originals_preserved") is not True or
            feedback.get("native_replay_requested") is not False):
        raise ValueError("Negative saved-source failure was not classified correctly")
    print("missing pass-context: recorded-only feedback passed", flush=True)


if __name__ == "__main__":
    main()
