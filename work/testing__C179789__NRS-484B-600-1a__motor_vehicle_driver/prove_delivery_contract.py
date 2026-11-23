"""Validate seven exact delivery audit bindings against the pinned contract."""
from __future__ import annotations

import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
private = os.environ.get("SCENARIO_PIPELINE_OUTPUT_ROOT", "")
if not private or not Path(private).resolve().is_relative_to(REPO / ".runtime-work"):
    raise RuntimeError("Export SCENARIO_PIPELINE_OUTPUT_ROOT under .runtime-work first")
sys.path.insert(0, str(REPO / "runtime/scenario_pipeline"))
from worker_exchange.delivery_handoff import validate_case


def main() -> None:
    manifest = json.loads((ROOT / "execution-manifest.json").read_text())
    if len(manifest["cases"]) != 7:
        raise ValueError("seven exact cases required")
    for entry in manifest["cases"]:
        validate_case(ROOT, entry, expected_sets=("full-test",))
        print(entry["case_id"], "delivery contract passed")


if __name__ == "__main__":
    main()
