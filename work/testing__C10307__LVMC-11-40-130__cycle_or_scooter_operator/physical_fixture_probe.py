"""Synthetic CPU proof for evidence-driven alley-route completion decisions."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

START_X = -30.0
END_X = 30.0
ROUTE_Y = -0.75
FRAMES = 900


def evaluate(spec_path: Path) -> dict:
    raw = spec_path.read_bytes()
    spec = json.loads(raw)
    case_id = spec.get("case_id")
    kind = spec.get("kind")
    if not isinstance(case_id, str) or not case_id.startswith(
        "testing__C10307__LVMC-11-40-130__cycle_or_scooter_operator__"
    ) or kind not in ("complete_motion", "incomplete_motion", "missing_evidence"):
        raise ValueError("exact synthetic fixture identity required")
    samples = spec.get("samples")
    if not isinstance(samples, list):
        raise ValueError("original-shaped motion samples required")
    complete_source = len(samples) == FRAMES
    prior = None
    for index, row in enumerate(samples):
        if not isinstance(row, dict) or not all(key in row for key in
            ("frame", "time_s", "x_m", "y_m", "velocity_mps")):
            complete_source = False
            break
        if row["frame"] != index or abs(row["time_s"] - (index + 1) / 20) > .001:
            complete_source = False
            break
        x, y, speed = row["x_m"], row["y_m"], row["velocity_mps"]
        if not all(type(value) in (int, float) and math.isfinite(value)
                   for value in (x, y, speed)) or abs(y - ROUTE_Y) > .8:
            complete_source = False
            break
        if prior is not None and x < prior - .05:
            complete_source = False
            break
        prior = x
    reached = (complete_source and samples[0]["x_m"] <= START_X + .5 and
               samples[-1]["x_m"] >= END_X and
               samples[-1]["x_m"] - samples[0]["x_m"] >= 59)
    status = "unverified" if not complete_source else "met" if reached else "not_met"
    return {
        "format": "worker-c10307-physical-cpu-fixture-v1",
        "case_id": case_id,
        "fixture_kind": kind,
        "provenance_kind": "synthetic_fixture",
        "diagnostic_fixture": True,
        "maneuver_completed": status == "met",
        "physical_checks": {"maneuver": {
            "status": status,
            "method": "900 original-shaped 20 Hz pose/velocity joins and measured -30 m to +30 m route endpoint",
            "sources": [{"path": spec_path.name, "sha256": hashlib.sha256(raw).hexdigest()}],
        }},
        "realized_observables": ({"route_start_x_m": samples[0]["x_m"],
                                  "route_end_x_m": samples[-1]["x_m"],
                                  "observed_frames": len(samples)} if status == "met" else {}),
        "legal_prudence": "unresolved",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--spec", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("physical fixture result already exists")
    result = evaluate(args.spec)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(result["case_id"], result["fixture_kind"], result["physical_checks"]["maneuver"]["status"])


if __name__ == "__main__":
    main()
