"""Author source-labeled CPU physical outcome fixtures for each exact case.

The source histories are temporary diagnostic data under .runtime-work; only
small derived receipts are returned. This does not simulate a CARLA pass.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from opposing_pass import VARIANTS
from physical_completion import assess


HERE = Path(__file__).resolve().parent
SCRATCH = HERE.parents[1] / ".runtime-work" / "c125714-2031-physical"


def trace(variant, kind):
    lateral = {"right_half": (-1.7, 1.7), "wrong_side": (1.7, -1.7),
               "left_encroachment": (-.7, 1.7),
               "right_constrained": (-1.5, 1.7)}[variant]
    rows = []
    for i in range(3):
        ego_s = [i-1, i+1]
        other_s = [1-i, 3-i] if kind == "complete_motion" else [20, 22]
        rows.append({"frame": i, "time_s": i/20,
            "ego_id": "diagnostic-ego", "other_id": "diagnostic-other",
            "ego_speed_s_mps": 6, "other_speed_s_mps": -6,
            "paved_y_bounds_m": [-3.5, 3.5],
            "ego_body_s_bounds_m": ego_s, "other_body_s_bounds_m": other_s,
            "ego_body_y_bounds_m": [lateral[0]-.6, lateral[0]+.6],
            "other_body_y_bounds_m": [lateral[1]-.6, lateral[1]+.6]})
    return {"source_kind": "original_native_actor_history",
        "map_source_kind": "original_native_map_geometry",
        "public_highway": True, "encounter_on_undivided_approach": True,
        "traffic_line_capacity_each_direction": [1, 1],
        "capacity_source": "synthetic fixture only", "paved_boundary_source": "synthetic fixture only",
        "actor_ids": ["diagnostic-ego", "diagnostic-other"],
        "samples": rows, "diagnostic_fixture": True}


def write(variant):
    if variant not in VARIANTS:
        raise ValueError("unknown exact case")
    scratch = SCRATCH / variant
    scratch.mkdir(parents=True, exist_ok=True)
    result_dir = HERE / "physical-fixtures" / variant
    result_dir.mkdir(parents=True, exist_ok=True)
    expected = {"complete_motion": "met", "incomplete_motion": "not_met",
                "missing_evidence": "unverified"}
    for kind, status in expected.items():
        source = scratch / (kind + ".json")
        if kind == "missing_evidence":
            if source.exists():
                source.unlink()
            digest = "0"*64
        else:
            source.write_text(json.dumps(trace(variant, kind), sort_keys=True) + "\n")
            digest = hashlib.sha256(source.read_bytes()).hexdigest()
        report = assess(source, digest)
        if report["physical_checks"]["maneuver"]["status"] != status:
            raise ValueError("diagnostic physical fixture did not produce declared outcome")
        report.update(provenance_kind="synthetic_fixture", diagnostic_fixture=True,
                      case_id=HERE.name + "__" + variant)
        (result_dir / (kind + ".json")).write_text(
            json.dumps(report, indent=2, sort_keys=True) + "\n")
        (result_dir / (kind + ".log")).write_text(
            "diagnostic " + variant + " " + kind + " assessed as " + status + "\n")


if __name__ == "__main__":
    for case_variant in VARIANTS:
        write(case_variant)
