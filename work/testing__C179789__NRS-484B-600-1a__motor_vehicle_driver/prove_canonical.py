"""Validate the current exact-case manifest with the pinned runtime contract."""
from __future__ import annotations

import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
private = os.environ.get("SCENARIO_PIPELINE_OUTPUT_ROOT", "")
if not private or not Path(private).resolve().is_relative_to(REPO / ".runtime-work"):
    raise RuntimeError("Export SCENARIO_PIPELINE_OUTPUT_ROOT under .runtime-work first")
sys.path.insert(0, str(REPO / "runtime/scenario_pipeline"))
from worker_exchange.execution_manifest import validate


def main() -> None:
    manifest = validate(REPO, ROOT.name)
    if len(manifest["cases"]) != 7:
        raise ValueError("seven exact canonical cases required")
    print("canonical execution manifest passed", len(manifest["cases"]))


if __name__ == "__main__":
    main()
