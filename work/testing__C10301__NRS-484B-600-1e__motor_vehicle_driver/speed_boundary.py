"""Source-bound 80 mph speed observations and controlled comparison.

These are engineering observations, not statutory verdicts. A sampled maximum
cannot rule out a peak between samples. Diagnostic fixtures never prove motion.
"""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

MPH_PER_MPS = 2.2369362920544
BOUNDARY_MPH = 80.0
EXPECTED_FRAMES = 900
EXPECTED_HZ = 20.0


def _read_json(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"invalid source document: {path.name}")
    return value


def _number(value: object, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"invalid {name}")
    return float(value)


def measure(attempt: Path, case_id: str) -> dict:
    """Read all original speed samples and a hash-bound Native source descriptor."""
    attempt = Path(attempt)
    descriptor = _read_json(attempt / "speed-source.json")
    if (descriptor.get("format") != "c10301-original-speed-source-v1" or
            descriptor.get("case_id") != case_id or
            descriptor.get("source") != "original-speed.jsonl" or
            descriptor.get("sample_rate_hz") != EXPECTED_HZ or
            descriptor.get("sample_count") != EXPECTED_FRAMES or
            not isinstance(descriptor.get("native_run_id"), str) or
            not descriptor["native_run_id"] or
            not isinstance(descriptor.get("source_frame_origin"), int) or
            descriptor["source_frame_origin"] < 0):
        raise ValueError("original speed descriptor incomplete or wrong case")
    raw = (attempt / "original-speed.jsonl").read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    if descriptor.get("sha256") != digest:
        raise ValueError("original speed source hash differs")
    rows = [json.loads(line) for line in raw.splitlines() if line.strip()]
    if len(rows) != EXPECTED_FRAMES:
        raise ValueError("original speed frame count differs")
    origin = descriptor["source_frame_origin"]
    speed_mph = []
    uncertainties_mph = []
    for index, row in enumerate(rows):
        if not isinstance(row, dict) or row.get("frame") != origin + index:
            raise ValueError("original speed frame sequence differs")
        time_s = _number(row.get("time_s"), "original time")
        if abs(time_s - index / EXPECTED_HZ) > 1e-6:
            raise ValueError("original speed sample time differs")
        value = _number(row.get("speed_mps"), "original speed")
        uncertainty = _number(row.get("speed_uncertainty_mps"), "speed uncertainty")
        if value < 0 or uncertainty < 0:
            raise ValueError("negative speed or uncertainty")
        speed_mph.append(value * MPH_PER_MPS)
        uncertainties_mph.append(uncertainty * MPH_PER_MPS)
    peak_index = max(range(EXPECTED_FRAMES), key=speed_mph.__getitem__)
    peak = speed_mph[peak_index]
    peak_uncertainty = uncertainties_mph[peak_index]
    min_lower = min(value - uncertainty for value, uncertainty in zip(speed_mph, uncertainties_mph))
    max_upper = max(value + uncertainty for value, uncertainty in zip(speed_mph, uncertainties_mph))
    if min_lower > BOUNDARY_MPH:
        sampled_relation = "all_samples_above"
    elif max_upper < BOUNDARY_MPH:
        sampled_relation = "all_samples_below"
    elif any(value - uncertainty > BOUNDARY_MPH for value, uncertainty in zip(speed_mph, uncertainties_mph)):
        sampled_relation = "some_sample_clearly_above"
    else:
        sampled_relation = "boundary_unresolved"
    return {
        "format": "c10301-speed-measurement-v1", "case_id": case_id,
        "native_run_id": descriptor["native_run_id"], "source": "original-speed.jsonl",
        "source_sha256": digest, "sample_count": EXPECTED_FRAMES,
        "sample_rate_hz": EXPECTED_HZ, "peak_sample_frame": origin + peak_index,
        "peak_sample_mph": peak, "peak_uncertainty_mph": peak_uncertainty,
        "sampled_relation": sampled_relation,
        "between_sample_peaks": "unobserved", "diagnostic_fixture": descriptor.get("diagnostic_fixture") is True,
        "physical_acceptance_claimed": False, "legal_judgment": "unresolved",
    }


def compare(plan_path: Path, attempts: dict[str, Path]) -> dict:
    """Check source identities, fixed settings and observed ordering for one triple."""
    plan_bytes = Path(plan_path).read_bytes()
    plan = json.loads(plan_bytes)
    comparison = next((item for item in plan.get("comparisons", [])
                       if item.get("comparison_id") == "strict_rate_boundary"), None)
    if comparison is None or len(comparison.get("case_ids", [])) != 3:
        raise ValueError("strict rate comparison needs three exact cases")
    case_ids = comparison["case_ids"]
    if set(attempts) != set(case_ids) or len({Path(p).resolve() for p in attempts.values()}) != 3:
        raise ValueError("three distinct exact case attempts required")
    setups = []
    measurements = []
    for case_id in case_ids:
        attempt = Path(attempts[case_id])
        setup = _read_json(attempt / "authored-setup.json")
        if setup.get("case_id") != case_id or setup.get("law_id") != "NRS-484B-600-1e":
            raise ValueError("authored setup identity differs")
        target = _number(setup.get("requested_speed_mph"), "requested speed")
        if target < 0:
            raise ValueError("negative requested speed")
        setups.append(setup)
        measurements.append(measure(attempt, case_id))
    fixed = set(setups[0]) - {"case_id", "requested_speed_mph"}
    if any(set(item) != set(setups[0]) or any(item[key] != setups[0][key] for key in fixed)
           for item in setups[1:]):
        raise ValueError("fixed authored setup differs")
    targets = [item["requested_speed_mph"] for item in setups]
    if not (targets[0] < BOUNDARY_MPH and targets[1] == BOUNDARY_MPH and
            targets[2] > BOUNDARY_MPH):
        raise ValueError("requested boundary probes differ")
    observed = [item["peak_sample_mph"] for item in measurements]
    if not observed[0] < observed[1] < observed[2]:
        raise ValueError("original sampled speed ordering differs")
    if len({item["native_run_id"] for item in measurements}) != 3:
        raise ValueError("comparison reuses an original Native run")
    return {
        "format": "c10301-speed-comparison-v1", "comparison_id": "strict_rate_boundary",
        "case_ids": case_ids, "plan_sha256": hashlib.sha256(plan_bytes).hexdigest(),
        "source_sha256": [item["source_sha256"] for item in measurements],
        "requested_speed_mph": targets, "peak_sample_mph": observed,
        "sampled_relations": [item["sampled_relation"] for item in measurements],
        "fixed_setup_passed": True, "observed_order_passed": True,
        "diagnostic_fixture": any(item["diagnostic_fixture"] for item in measurements),
        "physical_acceptance_claimed": False, "legal_judgment": "unresolved",
    }
