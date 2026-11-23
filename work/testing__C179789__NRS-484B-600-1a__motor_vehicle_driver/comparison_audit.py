"""Independent source-bound check of authored and observed comparison isolation.

This checks engineering evidence only; reasonable/proper speed stays unresolved.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

from saved_conditions import measure


OBSERVED = {
    "speed": "ego_speed_mps",
    "traffic": "leader_gap_m",
    "surface": "surface_wetness",
    "width": "highway_width_m",
    "weather": "precipitation_strength",
    "visibility": "fog_density",
}
DIRECTION = {"speed": 1, "traffic": -1, "surface": 1,
             "width": -1, "weather": 1, "visibility": 1}


def _read_setup(attempt: Path, case_id: str) -> tuple[dict, str]:
    path = attempt / "authored-setup.json"
    data = path.read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    seal = json.loads((attempt / "authored-setup-seal.json").read_bytes())
    if seal != {"format": "c179789-authored-setup-v1", "case_id": case_id, "sha256": digest}:
        raise ValueError("authored setup seal or case identity differs")
    setup = json.loads(data)
    if setup.get("case_id") != case_id or not isinstance(setup.get("variables"), dict):
        raise ValueError("authored setup identity or variables missing")
    if set(setup["variables"]) != {
        "ego_speed_request_mps", "leader_initial_gap_m", "surface_wetness_request",
        "highway_width_m", "native_precipitation_request", "native_fog_request",
    }:
        raise ValueError("authored setup variables incomplete")
    for name, value in setup["variables"].items():
        if isinstance(value, bool) or not isinstance(value, (float, int)) or not math.isfinite(value) or value < 0:
            raise ValueError(f"invalid authored setup variable: {name}")
    for name in ("vehicle_blueprint", "travel_direction", "paved_road", "camera_profile", "duration_frames"):
        if name not in setup or setup[name] in (None, ""):
            raise ValueError(f"fixed authored setup missing: {name}")
    if setup["paved_road"] is not True:
        raise ValueError("paved road condition differs")
    return setup, digest


def audit(plan_path: Path, comparison_id: str, reference: Path, alternative: Path) -> dict:
    """Require two distinct sealed originals and only the declared setup change."""
    plan_bytes = Path(plan_path).read_bytes()
    plan = json.loads(plan_bytes)
    comparison = next((item for item in plan["comparisons"]
                       if item["comparison_id"] == comparison_id), None)
    if comparison is None or comparison_id not in OBSERVED:
        raise ValueError("unknown exact comparison")
    if Path(reference).resolve() == Path(alternative).resolve():
        raise ValueError("comparison attempts must be distinct")
    first_id, second_id = comparison["case_ids"]
    first_setup, first_hash = _read_setup(Path(reference), first_id)
    second_setup, second_hash = _read_setup(Path(alternative), second_id)
    difference = comparison["deliberate_differences"]
    if len(difference) != 1 or difference[0] not in first_setup["variables"]:
        raise ValueError("comparison declares an invalid authored difference")
    variable = difference[0]
    fixed = set(first_setup) - {"case_id", "variables"}
    if set(first_setup) != set(second_setup) or any(first_setup[key] != second_setup[key] for key in fixed):
        raise ValueError("fixed authored setup differs")
    changed = {key for key in first_setup["variables"]
               if first_setup["variables"][key] != second_setup["variables"][key]}
    if changed != {variable}:
        raise ValueError("declared comparison variable is not isolated")
    if DIRECTION[comparison_id] * (second_setup["variables"][variable] -
                                   first_setup["variables"][variable]) <= 0:
        raise ValueError("authored comparison direction differs")
    first = measure(reference, first_id)
    second = measure(alternative, second_id)
    if first["diagnostic_fixture"] or second["diagnostic_fixture"]:
        raise ValueError("diagnostic condition samples cannot prove a comparison")
    source_a, source_b = first["source_ids"], second["source_ids"]
    for key in ("road_id", "lane_id"):
        if source_a[key] != source_b[key] and comparison_id != "width":
            raise ValueError("roadway or travel lane differs")
    if source_a["opendrive_sha256"] != source_b["opendrive_sha256"] and comparison_id != "width":
        raise ValueError("OpenDRIVE source differs")
    if first["sample_count"] != second["sample_count"]:
        raise ValueError("observation window length differs")
    field = OBSERVED[comparison_id]
    measured_a = first["summary"][field]["mean"]
    measured_b = second["summary"][field]["mean"]
    if math.isclose(measured_a, measured_b, abs_tol=1e-9):
        raise ValueError("declared difference is absent from original measured conditions")
    if DIRECTION[comparison_id] * (measured_b - measured_a) <= 0:
        raise ValueError("measured comparison direction differs")
    return {
        "format": "c179789-comparison-audit-v1", "comparison_id": comparison_id,
        "case_ids": [first_id, second_id], "plan_sha256": hashlib.sha256(plan_bytes).hexdigest(),
        "authored_variable": variable, "observed_field": field,
        "setup_sha256": [first_hash, second_hash],
        "condition_sha256": [first["source"]["sha256"], second["source"]["sha256"]],
        "observed_means": [measured_a, measured_b],
        "fixed_setup_passed": True, "observed_difference_passed": True,
        "legal_judgment": "unresolved", "physical_acceptance_claimed": False,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("plan", type=Path)
    parser.add_argument("comparison_id")
    parser.add_argument("reference", type=Path)
    parser.add_argument("alternative", type=Path)
    args = parser.parse_args()
    print(json.dumps(audit(args.plan, args.comparison_id, args.reference, args.alternative), indent=2))
