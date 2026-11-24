"""Reprocess selected source-shaped fixtures against frozen active manifests."""

import concurrent.futures
import json
import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PKG = Path(__file__).resolve().parent
SCRATCH = ROOT / ".runtime-work" / "owner129-current" / "resaved-final"
VALIDATOR = ROOT / ".runtime-work/owner199/decoder-current/.lake/build/bin/adapterCheck"
DISTANCES = (90, 100, 110, 290, 300, 310)
CANDIDATES = ("primary", "fallback1", "fallback2")


def prove(item):
    distance, candidate = item
    tag = f"{distance}-{candidate}"
    manifest = (PKG / f"current-selected-{distance}-fallback1-proof-manifest.json"
                if candidate == "fallback1" else PKG / "execution-manifest.json")
    case_id = f"{PKG.name}__{distance}"
    recipe = PKG / f"current-{distance}-graph-recipe.json"
    if candidate == "fallback1":
        recipe = PKG / f"current-{distance}-fallback1-graph-recipe.json"
    fixture = SCRATCH / f"fixture-{tag}"
    attempt = SCRATCH / f"attempt-{tag}"
    saved = SCRATCH / f"saved-{tag}"
    env = os.environ.copy()
    env.update(PYTHONDONTWRITEBYTECODE="1", TMPDIR=str(ROOT / ".runtime-work"),
               SCENARIO_PIPELINE_OUTPUT_ROOT=str(SCRATCH / f"env-{tag}"),
               MPLCONFIGDIR=str(SCRATCH / "mpl"))
    sys.path.insert(0, str(ROOT / "runtime/scenario_pipeline"))
    from worker_exchange.fixture_recipe import materialize
    from worker_exchange.package_compatibility import materialize_case

    materialize(ROOT, recipe, fixture)
    materialize_case(manifest, case_id, attempt, fixture, candidate)
    command = [str(ROOT / ".venv-cpu/bin/python"), str(ROOT / "runtime.py"),
               "process-saved", "--manifest", str(manifest), "--case", case_id,
               "--library", str(ROOT / "runtime/library"), "--validator", str(VALIDATOR),
               "--attempt", str(attempt), "--output", str(saved)]
    completed = subprocess.run(command, cwd=ROOT, env=env, capture_output=True)
    if completed.returncode:
        (PKG / f"current-final-{tag}-saved-error.log").write_bytes(
            completed.stdout[-100000:] + completed.stderr[-100000:])
        return tag, "failed"
    receipt = json.loads(completed.stdout)
    if not receipt.get("passed") or not receipt.get("recorded_only"):
        return tag, "incomplete"
    (PKG / f"current-final-{tag}-saved-receipt.json").write_bytes(completed.stdout)
    return tag, "passed"


def main():
    SCRATCH.mkdir(parents=True, exist_ok=True)
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        for tag, status in pool.map(prove, ((d, c) for d in DISTANCES for c in CANDIDATES)):
            print(tag, status, flush=True)


if __name__ == "__main__":
    main()
