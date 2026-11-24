"""Run pinned recorded-only processing on one closed synthetic diagnostic fixture."""
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
MANIFEST = HERE / "execution-manifest.json"


def command(*args: str) -> None:
    subprocess.run([sys.executable, str(REPO / "runtime.py"), *map(str, args)],
                   cwd=REPO, check=True, stdout=subprocess.DEVNULL, timeout=900)


def prove(case_id: str) -> dict:
    suffix = case_id.removeprefix(HERE.name + "__")
    if suffix == case_id:
        raise ValueError("Exact case required")
    root = REPO / ".runtime-work/c109035-saved-proof" / suffix
    if root.exists():
        shutil.rmtree(root)
    root.mkdir(parents=True)
    source, attempt, output = root / "source", root / "attempt", root / "versions"
    recipe = HERE / "fixtures" / suffix / "recipe.json"
    command("fixture", "--recipe", recipe, "--output", source)
    command("materialize", "--manifest", MANIFEST, "--case", case_id,
            "--output", attempt)
    for path in source.iterdir():
        target = attempt / path.name
        if target.exists():
            raise ValueError("Fixture shadows selected package")
        if path.is_dir():
            shutil.copytree(path, target)
        else:
            shutil.copy2(path, target)
    marker = json.loads((attempt / "acquisition-provenance.json").read_text())
    if marker.get("provenance_kind") != "synthetic_fixture":
        raise ValueError("Diagnostic fixture provenance differs")
    before = {path.relative_to(attempt).as_posix(): path.read_bytes()
              for path in attempt.rglob("*") if path.is_file()}
    command("process-saved", "--manifest", MANIFEST, "--case", case_id,
            "--attempt", attempt, "--output", output,
            "--library", REPO / "runtime/library",
            "--validator", REPO / ".runtime-work/c179789-decoder/.lake/build/bin/adapterCheck")
    after = {path.relative_to(attempt).as_posix(): path.read_bytes()
             for path in attempt.rglob("*") if path.is_file()}
    if before != after:
        raise ValueError("Recorded-only processing changed source bytes")
    receipt = json.loads((output / "v0001/processing.json").read_text())
    if (not receipt.get("passed") or not receipt.get("recorded_only") or
            not receipt.get("originals_preserved") or receipt.get("missing_evidence")):
        raise ValueError("Saved-only processing receipt incomplete")
    return {"case_id": case_id, "recorded_only": True,
            "originals_preserved": True, "version": "v0001",
            "physical_acceptance_claimed": False}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("case_id")
    args = parser.parse_args()
    print(json.dumps(prove(args.case_id), sort_keys=True))
