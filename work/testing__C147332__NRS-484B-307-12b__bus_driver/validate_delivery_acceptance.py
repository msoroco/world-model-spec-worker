"""Apply pinned execution, compatibility and independent case validators."""
from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
sys.path[:0] = [str(REPO / "runtime"), str(REPO / "runtime/scenario_pipeline")]
from scenario_pipeline.worker_exchange import (delivery_handoff, execution_manifest,
                                               package_compatibility)


def main() -> None:
    manifest = json.loads((ROOT / "execution-manifest.json").read_text())
    execution_manifest.validate(REPO, ROOT.name)
    package_compatibility.check_receipts(REPO, ROOT, manifest)
    for entry in manifest["cases"]:
        delivery_handoff.validate_case(ROOT, entry, expected_sets=("full-test",))
        print(entry["case_id"] + ": exact independent delivery contract accepted")


if __name__ == "__main__":
    main()
