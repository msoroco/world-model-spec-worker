"""Independently verify all selected primary compatibility receipt bindings."""

import json
import os
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def main():
    output = os.environ.get("SCENARIO_PIPELINE_OUTPUT_ROOT", "")
    if not output or not Path(output).resolve().is_relative_to(ROOT / ".runtime-work"):
        raise ValueError("Set SCENARIO_PIPELINE_OUTPUT_ROOT under .runtime-work")
    from scenario_pipeline.worker_exchange.package_compatibility import check_receipts

    manifest = json.loads((HERE / "execution-manifest.json").read_text())
    check_receipts(ROOT, HERE, manifest)
    print("all selected primary compatibility receipts passed static verification", len(manifest["cases"]))


if __name__ == "__main__":
    main()
