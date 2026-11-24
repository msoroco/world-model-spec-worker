"""Reproduce one exact saved-only diagnostic processing proof in scratch."""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
SCRATCH = REPO / ".runtime-work"


def prove(case: str, tag: str) -> dict:
    output_root = Path(os.environ.get("SCENARIO_PIPELINE_OUTPUT_ROOT", "")).resolve()
    if not output_root.is_relative_to(SCRATCH) or not tag.isidentifier():
        raise ValueError("Set a .runtime-work output root and a simple scratch tag")
    sys.path[:0] = [str(REPO / "runtime"), str(REPO / "runtime/scenario_pipeline")]
    from scenario_pipeline.worker_exchange.runtime_cli import materialize
    from scenario_pipeline.worker_exchange.fixture_recipe import materialize as fixture_materialize
    from scenario_pipeline.worker_exchange.saved_processing import copy_sources, run

    manifest = HERE / "execution-manifest.json"
    entry = next((item for item in json.loads(manifest.read_text())["cases"]
                  if item["case_id"] == case), None)
    if entry is None:
        raise ValueError("Select one executable exact case")
    suffix = case.rsplit("__", 1)[-1]
    stem = f"c129731-saved-{suffix}-{tag}"
    fixture, attempt, output = (SCRATCH / (stem + "-" + kind)
                                for kind in ("fixture", "attempt", "output"))
    fixture_materialize(REPO, REPO / entry["fixture_recipe"], fixture)
    materialize(manifest, case, attempt)
    copy_sources(fixture, attempt)
    receipt = run(manifest, case, attempt, output, REPO / "runtime/library",
                  REPO / ".runtime-work/c129731-decoder-v1/.lake/build/bin/adapterCheck")
    if (receipt.get("passed") is not True or receipt.get("recorded_only") is not True
            or receipt.get("originals_preserved") is not True
            or receipt.get("physical_acceptance_claimed") is not False
            or receipt.get("legal_acceptance_claimed") is not False):
        raise ValueError("Saved-only proof failed")
    return receipt


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", required=True)
    parser.add_argument("--tag", default="repro")
    args = parser.parse_args()
    print(json.dumps(prove(args.case, args.tag), indent=2))


if __name__ == "__main__":
    main()
