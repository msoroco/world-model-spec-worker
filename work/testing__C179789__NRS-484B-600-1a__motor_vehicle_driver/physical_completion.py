"""Source-bound diagnostic motion classification for a closed Native trace.

This measures motion only. A synthetic trace cannot establish real road geometry,
camera visibility, or the legal judgment under NRS 484B.600(1)(a).
"""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def classify(trace: Path, seal: Path, case_id: str) -> dict:
    """Require a matching source seal, then distinguish motion from missing data."""
    sources = {str(trace): digest(trace) if trace.is_file() else "missing",
               str(seal): digest(seal) if seal.is_file() else "missing"}
    result = {"provenance_kind": "synthetic_fixture", "diagnostic_fixture": True,
              "physical_acceptance_claimed": False,
              "maneuver_completed": False, "realized_observables": {},
              "physical_checks": {"maneuver": {
                  "status": "unverified", "method": "sealed 900-frame position trace; endpoint displacement >= 0.25 m",
                  "sources": sources}}}
    if not trace.is_file() or not seal.is_file():
        return result
    try:
        declared = json.loads(seal.read_text(encoding="utf-8"))
        rows = [json.loads(line) for line in trace.read_text(encoding="utf-8").splitlines()]
        if (declared.get("case_id") != case_id or
                declared.get("trace_sha256") != digest(trace) or len(rows) != 900):
            return result
        for index, row in enumerate(rows):
            point = row.get("position_m")
            if (row.get("frame") != index or not isinstance(point, list) or
                    len(point) != 3 or any(type(v) not in (int, float) or
                                            not math.isfinite(v) for v in point)):
                return result
        displacement = math.dist(rows[0]["position_m"], rows[-1]["position_m"])
    except (ValueError, TypeError, KeyError, UnicodeError):
        return result
    met = displacement >= 0.25
    result["maneuver_completed"] = met
    result["physical_checks"]["maneuver"]["status"] = "met" if met else "not_met"
    result["realized_observables"] = {"endpoint_displacement_m": displacement,
                                      "frame_count": len(rows)}
    return result
