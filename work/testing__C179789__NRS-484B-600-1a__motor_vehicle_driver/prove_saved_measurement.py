"""Reproduce the diagnostic saved-finalizer and pinned Native schema proof."""

from __future__ import annotations

import json
import os
from pathlib import Path
import sys
import tempfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
private = (ROOT / ".runtime-work").resolve()
output_root = os.environ.get("SCENARIO_PIPELINE_OUTPUT_ROOT")
if (not output_root or private not in Path(output_root).resolve().parents):
    raise ValueError("export SCENARIO_PIPELINE_OUTPUT_ROOT under .runtime-work before runtime import")
sys.path[:0] = [str(HERE), str(HERE / "tests"), str(ROOT / "runtime/scenario_pipeline")]

from saved_measurement import finalize_attempt
from test_saved_measurement import fixture
from worker_exchange.native_output import validate_result


with tempfile.TemporaryDirectory(dir=private) as directory:
    attempt = Path(directory) / "attempt"
    fixture(attempt)
    report = finalize_attempt(attempt, attempt / "analysis-report.json")
    native = json.loads((attempt / "result.json").read_text())
    validate_result(native)
    if (report["measurements"]["basic_speed_observation"]["value"]["legal_judgment"]
            != "unresolved" or native["physical_acceptance_claimed"] is not False or
            native["measured_values"]["conditions"]["diagnostic_fixture"] is not True):
        raise ValueError("diagnostic saved measurement falsely claims physical/legal result")
    print("diagnostic saved finalizer and pinned Native result schema passed")
