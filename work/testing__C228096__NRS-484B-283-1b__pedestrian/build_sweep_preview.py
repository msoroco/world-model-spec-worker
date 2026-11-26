"""Build an engineering-only preview of two finite judgment sampling grids.

This is deliberately separate from proposals/cases.json until each expanded
case has an exact construction, source-bound CPU proofs and manifest entry.
"""
from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

from sweep_construction import STATIONS


ROOT = Path(__file__).resolve().parent


def preview() -> dict:
    proposal = json.loads((ROOT / "proposals/cases.json").read_text(encoding="utf-8"))
    proposal["cases"] = [case for case in proposal["cases"] if not case.get("sweep_id")]
    proposal["comparisons"] = [comparison for comparison in proposal["comparisons"]
                               if not comparison["comparison_id"].startswith("sweep_")]
    source = next(c for c in proposal["cases"] if c.get("target_type") == "boundary_probe")
    grids = []
    for item in proposal["sweep_specs"]:
        name = item["sweep_id"].rsplit("__", 1)[-1]
        points = [s for s in STATIONS if s.sweep == name]
        if len(points) != 3 or [s.value_m_or_s for s in points] != sorted(
                s.value_m_or_s for s in points):
            raise ValueError("three ordered authored engineering stations required")
        axis_name = "departure_hold_s" if name == "sudden_departure" else "vehicle_start_gap_m"
        measurement = ("first original post-hold pedestrian motion frame divided by 20 Hz"
                       if name == "sudden_departure" else
                       "original synchronized pedestrian and vehicle positions at first road-entry frame")
        values = deepcopy(source["variable_assignments"])
        values[axis_name] = {"kind": "controller", "value": points[0].value_m_or_s,
                             "unit": points[0].unit,
                             "note": "Authored physical setpoint; measure actual motion separately"}
        grids.append({"status": "complete", "sweep_id": item["sweep_id"],
                      "target_law_id": item["target_law_id"],
                      "judgment_refs": deepcopy(item["judgment_refs"]),
                      "mode": "one_dimensional", "landmarks": [],
                      "rationale": "Three bounded controller requests to sample physical behavior; legal phrase remains unresolved.",
                      "recording_description": deepcopy(source["recording_description"]),
                      "variable_assignments": values,
                      "axes": [{"variable": axis_name,
                                "observable": points[0].observable,
                                "unit": points[0].unit,
                                "min": points[0].value_m_or_s,
                                "max": points[-1].value_m_or_s,
                                "spacing": points[1].value_m_or_s - points[0].value_m_or_s,
                                "measurement": {"method": measurement,
                                                "time_window": "all 900 original 20 Hz frames",
                                                "statistic": "first"},
                                "range_rationale": "Bounded by the authored 45-second diagnostic episode and source-gated route controller; these values are not legal cutoffs or claimed original outcomes.",
                                "spacing_rationale": "Three distinguishable controller requests across the authored bounded interval; realized samples require original source review.",
                                "feasibility_evidence": "sweep_construction.py and test_sweep_construction.py exercise all six source-shaped controller requests; CARLA realization is pending."}]})
    proposal["sweep_specs"] = grids
    proposal["sweeps_expanded"] = False
    proposal["engineering_preview_only"] = True
    return proposal


def main() -> None:
    result = preview()
    target = ROOT / "sweep-preview.json"
    target.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print("Built six-station engineering preview; selected proposal remains incomplete")


if __name__ == "__main__":
    main()
