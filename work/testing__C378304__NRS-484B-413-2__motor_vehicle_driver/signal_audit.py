"""Independent saved-source and controlled-comparison audit.

The audit checks measurement reproducibility. It deliberately leaves physical
realization and statutory interpretation for independent review.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("signal_measure", HERE / "signal_measure.py")
MEASURE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MEASURE)


def audit_measurement(measurement_path: str | Path, source_path: str | Path) -> dict:
    saved = json.loads(Path(measurement_path).read_text())
    if saved.get("format") != "turn-signal-measurement-v1":
        raise ValueError("wrong measurement format")
    expected_case = saved.get("case_id")
    if not isinstance(expected_case, str) or not expected_case:
        raise ValueError("missing case identity")
    actual = MEASURE.measure(source_path, expected_case)
    # Paths can move between scratch and local processing, but the source
    # bytes and every measured field must remain identical.
    saved_without_path = {k: v for k, v in saved.items() if k != "source_path"}
    actual_without_path = {k: v for k, v in actual.items() if k != "source_path"}
    if saved_without_path != actual_without_path:
        raise ValueError("measurement differs from sealed source")
    return {"format": "turn-signal-audit-v1", "case_id": expected_case,
            "source_sha256": actual["source_sha256"], "passed": True}


def audit_comparison(left_measurement: str | Path, left_source: str | Path,
                     right_measurement: str | Path, right_source: str | Path,
                     comparison_id: str) -> dict:
    audit_measurement(left_measurement, left_source)
    audit_measurement(right_measurement, right_source)
    left = json.loads(Path(left_measurement).read_text())
    right = json.loads(Path(right_measurement).read_text())
    return MEASURE.compare(left, right, comparison_id)
