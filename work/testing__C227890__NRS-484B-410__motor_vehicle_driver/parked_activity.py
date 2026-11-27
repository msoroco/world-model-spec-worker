"""Measure source-sealed original parked departure without a legal verdict."""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

PREFIX = "testing__C227890__NRS-484B-410__motor_vehicle_driver__"


def _need(condition, message):
    if not condition:
        raise ValueError(message)


def _number(value, label):
    _need(type(value) in (int, float) and math.isfinite(value), "invalid original " + label)
    return float(value)


def _point(value, label):
    _need(isinstance(value, list) and len(value) == 2, "missing original " + label)
    return [_number(value[0], label), _number(value[1], label)]


def _spans(indices):
    if not indices:
        return []
    spans = []
    start = previous = indices[0]
    for index in indices[1:]:
        if index != previous + 1:
            spans.append([start / 20, (previous + 1) / 20])
            start = index
        previous = index
    spans.append([start / 20, (previous + 1) / 20])
    return spans


def measure_original_activity(history, seal, case_id, *, diagnostic=False):
    _need(case_id.startswith(PREFIX), "wrong parked-departure case")
    history, seal = Path(history), Path(seal)
    _need(history.is_file() and seal.is_file() and not history.is_symlink() and
          not seal.is_symlink(), "missing original activity source")
    raw = history.read_bytes()
    inventory = json.loads(seal.read_text())
    count = 9 if diagnostic else 900
    fmt = "diagnostic-parked-activity-seal" if diagnostic else "original-parked-activity-seal"
    source = "synthetic_fixture" if diagnostic else "original_native"
    _need(inventory.get("format") == fmt and inventory.get("case_id") == case_id,
          "original activity identity mismatch")
    _need(inventory.get("frame_count") == count and inventory.get("rate_hz") == 20 and
          inventory.get("history_sha256") == hashlib.sha256(raw).hexdigest(),
          "original activity seal mismatch")
    rows = [json.loads(line) for line in raw.splitlines()]
    _need(len(rows) == count, "original activity frame count mismatch")
    parked, moving, approach, overlap, exchange, driver = ([] for _ in range(6))
    distances, other_speeds, ego_speeds = [], [], []
    for index, row in enumerate(rows):
        _need(row.get("source_kind") == source and row.get("case_id") == case_id and
              row.get("frame") == index, "original activity frame identity mismatch")
        _need(abs(_number(row.get("time_s"), "time") - index / 20) < 1e-5,
              "original activity time discontinuity")
        ego_xy = _point(row.get("ego_center_xy_m"), "ego center")
        other_xy = _point(row.get("other_center_xy_m"), "other center")
        speed = _number(row.get("ego_speed_mps"), "ego speed")
        other_speed = _number(row.get("other_speed_mps"), "other speed")
        _need(speed >= 0 and other_speed >= 0, "negative original speed")
        for field in ("ego_in_reviewed_parking_bay", "ego_on_public_highway",
                      "parking_permitted_at_time", "driver_in_control",
                      "other_approaching", "paths_overlap", "passenger_exchange",
                      "goods_exchange"):
            _need(type(row.get(field)) is bool, "missing original " + field)
        _need(row["ego_on_public_highway"] and row["parking_permitted_at_time"],
              "original highway or parking basis absent")
        _need(row["driver_in_control"], "original driver control absent")
        if row["ego_in_reviewed_parking_bay"] and speed < 0.1:
            parked.append(index)
        if speed >= 0.1:
            moving.append(index)
        if row["other_approaching"]:
            approach.append(index)
        if row["paths_overlap"]:
            overlap.append(index)
        if row["passenger_exchange"] or row["goods_exchange"]:
            exchange.append(index)
        driver.append(row["driver_in_control"])
        distances.append(math.dist(ego_xy, other_xy))
        ego_speeds.append(speed)
        other_speeds.append(other_speed)
    _need(parked and parked[0] == 0, "vehicle was not initially parked")
    _need(not exchange, "passenger or goods exchange changes selected branch")
    return {
        "format": "diagnostic-parked-activity-measurements" if diagnostic else "original-parked-activity-measurements",
        "case_id": case_id, "history_sha256": hashlib.sha256(raw).hexdigest(),
        "frame_count": count, "rate_hz": 20,
        "intervals_s": {"parked": _spans(parked), "moving": _spans(moving),
                        "other_approaching": _spans(approach), "paths_overlap": _spans(overlap)},
        "body_center_gap_min_m": min(distances),
        "ego_speed_max_mps": max(ego_speeds),
        "other_speed_max_mps": max(other_speeds),
        "driver_control_frames": sum(driver),
        "legal_safety_conclusion": "unreviewed",
    }
