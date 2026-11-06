"""Saved Native-sample measurement of continuous pre-turn signaling.

Rows are observed-source shaped; a synthetic fixture never becomes an original
Native observation merely by passing this measurement.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path


def measure(path: Path, *, expected_sha256: str, area: str,
            expected_onset_frame: int | None = None,
            expected_course_change_frame: int | None = None) -> dict:
    if area not in ("business_or_residential", "other"):
        raise ValueError("area classification missing")
    raw = path.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    if digest != expected_sha256:
        raise ValueError("source hash mismatch")
    rows = [json.loads(line) for line in raw.splitlines() if line.strip()]
    if len(rows) < 3:
        raise ValueError("insufficient samples")
    first_time = float(rows[0].get("time_s", -1))
    for i, row in enumerate(rows):
        if row.get("frame") != i or abs(float(row.get("time_s", -1)) - (first_time + i / 20)) > 1e-4:
            raise ValueError("frame/time discontinuity")
        if row.get("area") != area or row.get("weather") not in ("clear", "rain"):
            raise ValueError("area or weather source missing")
        if row.get("signal") not in ("left", "off") or row.get("course_change") not in (True, False):
            raise ValueError("signal or turn source missing")
        xy = row.get("ego_xy_m")
        if not isinstance(xy, list) or len(xy) != 2 or not all(isinstance(v, (int, float)) and math.isfinite(v) for v in xy):
            raise ValueError("pose source missing")
        heading = row.get("heading_deg")
        if type(heading) not in (int, float) or not math.isfinite(heading) or not -90 <= heading <= 0:
            raise ValueError("heading source missing")
    turns = [i for i, row in enumerate(rows) if row["course_change"]]
    if len(turns) != 1:
        raise ValueError("one observed course change required")
    turn = turns[0]
    if turn < 2 or turn >= len(rows) - 1 or rows[turn]["signal"] != "left":
        raise ValueError("signal absent at course change")
    if turn + 25 >= len(rows) or rows[turn - 1]["heading_deg"] != 0 or rows[turn + 25]["heading_deg"] >= -30:
        raise ValueError("course change lacks observed heading transition")
    start = turn
    while start > 0 and rows[start - 1]["signal"] == "left":
        start -= 1
    if ((expected_onset_frame is not None and start != expected_onset_frame) or
            (expected_course_change_frame is not None and turn != expected_course_change_frame)):
        raise ValueError("observed signal interval differs from contract")
    if start == 0:
        raise ValueError("signal onset outside capture")
    distance_m = 0.0
    for i in range(start + 1, turn + 1):
        a, b = rows[i - 1]["ego_xy_m"], rows[i]["ego_xy_m"]
        step = math.hypot(b[0] - a[0], b[1] - a[1])
        if not 0 < step < 1:
            raise ValueError("implausible or missing path step")
        distance_m += step
    return {"format": "c329610-413-2-saved-signal-v1", "source_sha256": digest,
            "area": area, "weather": rows[turn]["weather"], "onset_frame": start,
            "course_change_frame": turn, "continuous_signal_distance_ft": distance_m / .3048,
            "threshold_ft": 100 if area == "business_or_residential" else 300,
            "sample_count": len(rows), "synthetic_or_original": "caller_must_prove",
            "limitations": ["sampled signal state only", "no intersample or physical Native claim", "no legal verdict"]}
