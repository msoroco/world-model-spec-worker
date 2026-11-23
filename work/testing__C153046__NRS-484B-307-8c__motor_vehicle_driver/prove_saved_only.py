"""Run pinned saved-only processing on eight sealed synthetic case fixtures."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import sys

from build_case_plan import AID, KINDS

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


def main() -> None:
    manifest = ROOT / "execution-manifest.json"
    entries = {entry["case_id"]: entry for entry in json.loads(manifest.read_text())["cases"]}
    validator = REPO / ".runtime-work/c109755-decoder-v2/.lake/build/bin/adapterCheck"
    if not validator.is_file():
        raise ValueError("pinned Lean validator missing")
    for suffix in KINDS:
        case = AID + "__" + suffix
        if case not in entries:
            raise ValueError("exact case missing from canonical manifest")
        base = REPO / ".runtime-work/c153046-saved-only" / suffix
        if base.exists():
            shutil.rmtree(base)
        base.mkdir(parents=True)
        fixture, attempt = base / "fixture", base / "attempt"
        fixture_materialize(REPO, ROOT / "diagnostics" / suffix / "fixture-recipe.json", fixture)
        construction_materialize(manifest, case, attempt)
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
        receipt = run(manifest, case, attempt, base / "saved", REPO / "runtime/library",
                      validator, owner)
        if (receipt.get("passed") is not True or receipt.get("recorded_only") is not True or
                receipt.get("missing_evidence") is not False or
                receipt["native_revision"]["construction_sha256"] != entries[case]["construction_sha256"]):
            raise ValueError("saved-only proof failed: " + case)
        log = ROOT / "diagnostics" / suffix / "saved-only-processing.json"
        log.write_text(json.dumps(receipt, indent=2) + "\n")
        print(case, "saved-only diagnostic processing passed", sha(log), flush=True)


if __name__ == "__main__":
    main()
