"""Preview a bounded physical walking-speed grid for the device exception.

The points are controller requests, not permission thresholds or observed
speeds. Original signal, highway, and device authority remain source gated.
"""
from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

from build_bundles import recording_description


ROOT = Path(__file__).resolve().parent
ASSIGNMENT = ROOT.name
POINTS = (0.8, 1.2, 1.6)
AXIS = "walk_speed_target_mps"
OBSERVABLE = "original_pedestrian_speed_mps"


def preview() -> dict:
    proposal = json.loads((ROOT / "proposals/cases.json").read_text())
    proposal["cases"] = [case for case in proposal["cases"] if not case.get("sweep_id")]
    proposal["comparisons"] = [c for c in proposal["comparisons"]
                               if not c["comparison_id"].startswith("sweep_walk_speed_")]
    for case in proposal["cases"]:
        case["recording_description"] = recording_description()
    source = next(c for c in proposal["cases"] if c.get("case_id", "").endswith("__enter_walk_display"))
    spec = proposal["sweep_specs"][0]
    values = deepcopy(source["variable_assignments"])
    values[AXIS] = {"kind": "controller", "unit": "m/s", "value": POINTS[0],
                    "note": "Physical controller request; actual original speed is measured separately"}
    proposal["sweep_specs"] = [{
        "status": "complete", "sweep_id": spec["sweep_id"],
        "target_law_id": spec["target_law_id"], "judgment_refs": spec["judgment_refs"],
        "mode": "one_dimensional", "landmarks": [],
        "rationale": "Sample finite pedestrian approach speeds while the separate device displays WALK; permission under NRS 484B.283 remains unresolved.",
        "recording_description": deepcopy(source["recording_description"]),
        "variable_assignments": values,
        "axes": [{"variable": AXIS, "observable": OBSERVABLE, "unit": "m/s",
                  "min": POINTS[0], "max": POINTS[-1], "spacing": 0.4,
                  "measurement": {"method": "original 20 Hz pedestrian body velocity readback after departure, retaining the complete raw stream",
                                  "time_window": "original seconds 6 through 12 after departure, excluding startup transient",
                                  "statistic": "mean"},
                  "range_rationale": "Three authored walking controller requests for the existing 45-second route and source-gated Native walker; no value defines legal permission.",
                  "spacing_rationale": "Three separated physical setpoints permit measured approach variation while maintaining the same signal, route and cameras.",
                  "feasibility_evidence": "NativeAdapter applies a source-gated walker control every original frame; local CPU tests exercise the three requests, while physical realization remains pending."}]
    }]
    proposal["sweeps_expanded"] = False
    proposal["engineering_preview_only"] = True
    return proposal


if __name__ == "__main__":
    value = preview()
    (ROOT / "sweep-preview.json").write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
    print("Built three-point source-gated walking-speed preview")
