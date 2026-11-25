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
                     comparison_id: str, above_measurement: str | Path | None = None,
                     above_source: str | Path | None = None) -> dict:
    audit_measurement(left_measurement, left_source)
    audit_measurement(right_measurement, right_source)
    left = json.loads(Path(left_measurement).read_text())
    right = json.loads(Path(right_measurement).read_text())
    if (above_measurement is None) != (above_source is None):
        raise ValueError("numeric triple needs both above measurement and source")
    above = None
    if above_measurement is not None:
        if comparison_id != "business_right_distance":
            raise ValueError("numeric triple applies only to business distance")
        audit_measurement(above_measurement, above_source)
        above = json.loads(Path(above_measurement).read_text())
    return MEASURE.compare(left, right, comparison_id, above)


def audit_selected_comparison(comparison_id: str, sources: list[tuple[str | Path, str | Path]]) -> dict:
    """Audit the exact frozen three-way or pairwise comparison case order."""
    plan = json.loads((HERE / "case-plan.json").read_text())
    rows = [item for item in plan["comparisons"] if item["comparison_id"] == comparison_id]
    if len(rows) != 1 or len(sources) != len(rows[0]["case_ids"]):
        raise ValueError("selected comparison source count differs")
    for pair, expected_id in zip(sources, rows[0]["case_ids"]):
        measurement = json.loads(Path(pair[0]).read_text())
        if measurement.get("case_id") != expected_id:
            raise ValueError("selected comparison case identity differs")
    left, right = sources[:2]
    above = sources[2] if len(sources) == 3 else None
    return audit_comparison(left[0], left[1], right[0], right[1], comparison_id,
                            above[0] if above else None, above[1] if above else None)
