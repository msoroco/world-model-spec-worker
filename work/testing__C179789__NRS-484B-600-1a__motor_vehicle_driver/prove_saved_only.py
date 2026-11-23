"""Run pinned saved-only conversion for seven sealed diagnostic acquisitions."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
PRIVATE = os.environ.get("SCENARIO_PIPELINE_OUTPUT_ROOT", "")
if not PRIVATE or not Path(PRIVATE).resolve().is_relative_to(REPO / ".runtime-work"):
    raise RuntimeError("Export SCENARIO_PIPELINE_OUTPUT_ROOT under .runtime-work first")
sys.path.insert(0, str(REPO / "runtime/scenario_pipeline"))
from worker_exchange.fixture_recipe import materialize as fixture_materialize
from worker_exchange.runtime_cli import materialize as construction_materialize
from worker_exchange.native_output import seal_capture
from worker_exchange.saved_processing import record_native_exit, acknowledge_owner_release, run


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def prove(entry: dict) -> None:
    case = entry["case_id"]
    suffix = case.removeprefix(ROOT.name + "__")
    if suffix == case:
        raise ValueError("case does not belong to assignment")
    recipe = ROOT / ("diagnostic-recipe.json" if suffix == "reference" else
                     "diagnostics/" + suffix + "/diagnostic-recipe.json")
    base = REPO / ".runtime-work/c179789-saved-only" / suffix
    if base.exists():
        shutil.rmtree(base)
    base.mkdir(parents=True)
    fixture, attempt = base / "fixture", base / "attempt"
    fixture_materialize(REPO, recipe, fixture)
    construction_materialize(ROOT / "execution-manifest.json", case, attempt)
    for item in fixture.iterdir():
        target = attempt / item.name
        if target.exists():
            raise ValueError("fixture shadows construction: " + item.name)
        if item.is_dir():
            shutil.copytree(item, target)
        else:
            shutil.copy2(item, target)
    (attempt / "acquisition-provenance.json").write_text(json.dumps({
        "provenance_kind": "synthetic_fixture", "diagnostic_fixture": True,
        "physical_acceptance_claimed": False,
    }) + "\n")
    frames = len((attempt / "trace.jsonl").read_text().splitlines())
    seal_capture(attempt, frames=frames,
                 restoration={"restored": True, "synthetic_fixture": True}, errors=[],
                 encoder_exit_codes={name: 0 for name in
                                     ("overview", "approach", "reference_corner", "driver_reference")})
    record_native_exit(attempt)
    owner = base / "owner-release.json"
    acknowledge_owner_release(attempt, owner, True)
    receipt = run(ROOT / "execution-manifest.json", case, attempt, base / "saved",
                  REPO / "runtime/library",
                  REPO / ".runtime-work/c179789-decoder/.lake/build/bin/adapterCheck", owner)
    if (receipt.get("passed") is not True or receipt.get("recorded_only") is not True or
            receipt.get("missing_evidence") is not False or
            receipt.get("originals_preserved") is not True or
            receipt["native_revision"]["construction_sha256"] != entry["construction_sha256"]):
        raise ValueError("saved-only diagnostic proof failed: " + case)
    log = ROOT / ("saved-only-processing.json" if suffix == "reference" else
                  "diagnostics/" + suffix + "/saved-only-processing.json")
    log.write_text(json.dumps(receipt, indent=2) + "\n")
    print(case, "saved-only diagnostic processing passed", sha(log), flush=True)


def main() -> None:
    manifest = json.loads((ROOT / "execution-manifest.json").read_text())
    cases = manifest["cases"]
    if len(cases) != 7 or len({entry["case_id"] for entry in cases}) != 7:
        raise ValueError("seven exact cases required")
    for entry in cases:
        prove(entry)


if __name__ == "__main__":
    main()
