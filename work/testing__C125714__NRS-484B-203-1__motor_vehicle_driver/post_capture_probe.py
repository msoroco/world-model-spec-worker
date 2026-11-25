"""CPU proof of saved-only processing with a source-bound owner receipt."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
SCRATCH = REPO / ".runtime-work" / "c125714-2031" / "post-capture-probe"
VALIDATOR = REPO / ".runtime-work" / "c125714-2031" / "validator" / ".lake" / "build" / "bin" / "adapterCheck"


def invoke(*args):
    return subprocess.run([sys.executable, str(REPO / "runtime.py"), *map(str, args)],
                          cwd=REPO, env=os.environ, capture_output=True, text=True)


def run(case, negative=False):
    if not case.startswith(HERE.name + "__"):
        raise ValueError("wrong exact saved-processing case")
    variant = case.rsplit("__", 1)[-1]
    if variant not in ("right_half", "wrong_side", "left_encroachment", "right_constrained"):
        raise ValueError("unknown exact saved-processing case")
    root = SCRATCH / variant / ("negative" if negative else "positive")
    if root.exists():
        shutil.rmtree(root)
    root.mkdir(parents=True)
    fixture, attempt, output = root / "fixture", root / "attempt", root / "output"
    manifest = HERE / "execution-manifest.json"
    recipe = HERE / "cases" / variant / "fixture-recipe.json"
    for step in (("fixture", "--recipe", recipe, "--output", fixture),
                 ("materialize", "--manifest", manifest, "--case", case, "--output", attempt)):
        completed = invoke(*step)
        if completed.returncode:
            raise ValueError("diagnostic source preparation failed: " + completed.stderr[-800:])
    for source in fixture.iterdir():
        target = attempt / source.name
        if target.exists():
            raise ValueError("diagnostic source shadows selected construction")
        if source.is_dir():
            shutil.copytree(source, target)
        else:
            shutil.copyfile(source, target)
    owner = root / "owner-release.json"
    released = invoke("owner-released", "--attempt", attempt, "--receipt", owner,
                      "--acknowledge-owner-released")
    if released.returncode:
        raise ValueError("diagnostic owner receipt failed: " + released.stderr[-800:])
    if negative:
        value = json.loads(owner.read_text())
        value["native_construction_sha256"] = "0" * 64
        owner.write_text(json.dumps(value, sort_keys=True) + "\n")
    completed = invoke("process-saved", "--manifest", manifest, "--case", case,
                       "--attempt", attempt, "--output", output,
                       "--library", REPO / "runtime" / "library", "--validator", VALIDATOR,
                       "--owner-release-receipt", owner)
    if negative:
        feedback = json.loads((output / "v0001" / "feedback.json").read_text())
        if completed.returncode == 0 or "Owner release not attested for this capture" not in feedback.get("error", ""):
            raise ValueError("changed owner receipt was not rejected")
        raise ValueError("Owner release not attested for this capture")
    if completed.returncode:
        raise ValueError("saved processing failed: " + completed.stderr[-1000:])
    receipt = json.loads((output / "v0001" / "processing.json").read_text())
    if (receipt.get("case_id") != case or receipt.get("recorded_only") is not True or
            receipt.get("originals_preserved") is not True or
            receipt.get("missing_evidence") is not False or
            receipt.get("physical_acceptance_claimed") is not False):
        raise ValueError("saved processing receipt incomplete")
    return {"case_id": case, "recorded_only": True, "originals_preserved": True,
            "analysis_complete": True, "diagnostic_fixture": True,
            "owner_receipt_checked": True, "physical_acceptance_claimed": False,
            "passed": True}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", required=True)
    parser.add_argument("--negative", action="store_true")
    args = parser.parse_args()
    print(json.dumps(run(args.case, args.negative), sort_keys=True))


if __name__ == "__main__":
    main()
