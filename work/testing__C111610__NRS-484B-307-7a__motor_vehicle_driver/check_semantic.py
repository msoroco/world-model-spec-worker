"""Validate the exact nine-stage proposal chain against pinned stage contracts."""
from __future__ import annotations

import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
AID = Path(__file__).resolve().parent.name


def main():
    output = Path(os.environ.get("SCENARIO_PIPELINE_OUTPUT_ROOT", "")).resolve()
    if output != ROOT / ".runtime-work" and ROOT / ".runtime-work" not in output.parents:
        raise ValueError("runtime pipeline output root must be under .runtime-work")
    sys.path.insert(0, str(ROOT / "runtime/scenario_pipeline"))
    from worker_exchange.semantic_delivery import validate
    folder = ROOT / "work" / AID
    assignment = json.loads((ROOT / "inputs" / AID / "assignment.json").read_text())
    manifest = json.loads((folder / "execution-manifest.draft.json").read_text())
    print(json.dumps(validate(folder, assignment, manifest), sort_keys=True))


if __name__ == "__main__":
    main()
