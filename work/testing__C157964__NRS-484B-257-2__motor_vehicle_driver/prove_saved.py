"""Exercise exact recorded-only processing on six synthetic officer sources."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
MANIFEST = ROOT / "execution-manifest.json"
SCRATCH = REPO / ".runtime-work/c157964-nov27"
DECODER = REPO / ".runtime-work/c150099-decoder-v2/.lake/build/bin/adapterCheck"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def command(*args):
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", TMPDIR=str(SCRATCH),
               SCENARIO_PIPELINE_OUTPUT_ROOT=str(SCRATCH))
    run = subprocess.run([sys.executable, str(REPO / "runtime.py"), *map(str, args)],
                         cwd=REPO, env=env, text=True,
                         stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    if run.returncode:
        raise ValueError(run.stdout[-1800:])


def main():
    manifest = json.loads(MANIFEST.read_text())
    for entry in manifest["cases"]:
        suffix = entry["case_id"].removeprefix(ROOT.name + "__")
        source = SCRATCH / ("saved-source-" + suffix + "-v1")
        fixture = SCRATCH / ("saved-fixture-" + suffix + "-v1")
        if source.exists() and fixture.exists() and suffix == "occupied_stop":
            continue
        if source.exists() or fixture.exists():
            raise ValueError("choose fresh saved source version: " + suffix)
        command("materialize", "--manifest", MANIFEST, "--case", entry["case_id"],
                "--output", source)
        command("fixture", "--recipe", REPO / entry["fixture_recipe"],
                "--output", fixture)
        for path in fixture.iterdir():
            destination = source / path.name
            if destination.exists():
                raise ValueError("fixture shadows materialized source: " + path.name)
            if path.is_dir():
                shutil.copytree(path, destination)
            else:
                shutil.copy2(path, destination)
    for entry in manifest["cases"]:
        suffix = entry["case_id"].removeprefix(ROOT.name + "__")
        source = SCRATCH / ("saved-source-" + suffix + "-v1")
        output = SCRATCH / ("saved-proof-" + suffix + "-v1")
        if not (output / "v0001/processing.json").is_file():
            command("process-saved", "--manifest", MANIFEST, "--case", entry["case_id"],
                    "--attempt", source, "--output", output,
                    "--library", REPO / "runtime/library", "--validator", DECODER)
        receipt = output / "v0001/processing.json"
        saved = ROOT / ("cpu-saved-" + suffix + ".json")
        shutil.copyfile(receipt, saved)
        proof = json.loads(saved.read_text())
        if proof.get("passed") is not True or proof.get("recorded_only") is not True or \
                proof.get("originals_preserved") is not True or \
                proof.get("case_id") != entry["case_id"]:
            raise ValueError("saved-only proof incomplete: " + suffix)
        entry["saved_diagnostic"] = {"receipt": saved.name, "sha256": sha(saved),
                                     "source": str(source.relative_to(REPO)),
                                     "physical_acceptance_claimed": False}
        print("saved-only passed", suffix, flush=True)
    MANIFEST.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
