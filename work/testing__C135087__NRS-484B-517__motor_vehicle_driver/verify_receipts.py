"""Independently verify every on-disk selected compatibility receipt."""
from __future__ import annotations

import json
import os
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
ROOT = (REPO / ".runtime-work").resolve()
configured = Path(os.environ["SCENARIO_PIPELINE_OUTPUT_ROOT"]).resolve()
if configured != ROOT and ROOT not in configured.parents:
    raise ValueError("runtime output must be under .runtime-work")
sys.path.insert(0, str(REPO / "runtime" / "scenario_pipeline"))
sys.path.insert(1, str(REPO / "runtime" / "python"))

from worker_exchange.package_compatibility import check_receipts  # noqa: E402

manifest = json.loads((HERE / "execution-manifest.json").read_text())
if check_receipts(REPO, HERE, manifest) is not True:
    raise ValueError("selected compatibility receipt verification failed")
print("all eight selected compatibility receipts and removed-source negatives verified")
