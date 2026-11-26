"""Engineering speed requests, never legal speed tolerance or outcome labels."""
from __future__ import annotations

import math


UNIT = {"mph": 0.44704, "km/h": 5 / 18, "m/s": 1.0}


def target_speed(site: dict, variables: dict) -> float:
    if site.get("unit") not in UNIT or type(site.get("rate")) not in (int, float):
        raise ValueError("reviewed posted rate and unit required")
    posted = site["rate"] * UNIT[site["unit"]]
    relation = variables["rate_relation"]
    if relation not in ("below", "equal", "above"):
        raise ValueError("unknown requested speed relation")
    # One m/s is an engineering separation for construction trials, not a legal
    # threshold or a claim that actual speed realizes the requested relation.
    target = posted + {"below": -1.0, "equal": 0.0, "above": 1.0}[relation]
    if not math.isfinite(target) or target < 0:
        raise ValueError("requested engineering target invalid")
    return target


def command(actual_mps: float, target_mps: float, gain: float) -> tuple[float, float]:
    if any(type(value) not in (int, float) or not math.isfinite(value)
           for value in (actual_mps, target_mps, gain)) or min(actual_mps, target_mps) < 0 or gain <= 0:
        raise ValueError("invalid measured speed or controller gain")
    error = (target_mps - actual_mps) * gain
    return min(max(error, 0.0), 1.0), min(max(-error, 0.0), 1.0)
