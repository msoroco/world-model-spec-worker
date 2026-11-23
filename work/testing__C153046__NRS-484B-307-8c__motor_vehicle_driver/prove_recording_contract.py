"""Validate the exact original channel description with the pinned stage rule."""
from __future__ import annotations

import os
from pathlib import Path
import sys

REPO = Path(__file__).resolve().parents[2]
OUTPUT = Path(os.environ.get("SCENARIO_PIPELINE_OUTPUT_ROOT", "")).resolve()
PRIVATE = (REPO / ".runtime-work").resolve()
if OUTPUT != PRIVATE and PRIVATE not in OUTPUT.parents:
    raise ValueError("export SCENARIO_PIPELINE_OUTPUT_ROOT under .runtime-work first")
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(REPO / "runtime" / "scenario_pipeline"))

from batch_pipeline.validation import recording_description
from recording_description import build

recording_description(build())
print("canonical recording description shape passed; eight original channels")
