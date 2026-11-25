"""Evidence-backed CPU outcomes for the freight stop checker.

All generated source rows are synthetic diagnostics. No original municipal
surface, commercial status, pixels, or CARLA movement is claimed.
"""

import argparse
import json
from pathlib import Path

from freight_contract import VARIANTS


ROOT = Path(__file__).resolve().parent


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", required=True)
    parser.add_argument("--kind", required=True,
                        choices=("complete_motion", "incomplete_motion", "missing_evidence"))
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    variant = args.case.removeprefix(ROOT.name + "__")
    if args.case != ROOT.name + "__" + variant or variant not in VARIANTS:
        raise ValueError("unknown exact freight case")
    target_inside = VARIANTS[variant]["in_zone"]
    target = 5.0 if target_inside else 15.0
    if args.kind == "complete_motion":
        rows = [{"frame": i, "time_s": i / 20,
                 "station_m": round(min(target, -5.0 + (target + 5.0) * i / 500), 4),
                 "speed_mps": 0.0 if i >= 500 else 0.4} for i in range(900)]
    elif args.kind == "incomplete_motion":
        rows = [{"frame": i, "time_s": i / 20,
                 "station_m": -5.0, "speed_mps": 0.0} for i in range(900)]
    else:
        rows = []
    complete = (len(rows) == 900 and all(row["frame"] == i and row["time_s"] == i / 20
                                           for i, row in enumerate(rows)) and
                rows[-1]["station_m"] == target and
                all(row["speed_mps"] <= 0.1 for row in rows[-400:]) and
                rows[-1]["station_m"] > rows[0]["station_m"])
    status = "unverified" if not rows else "met" if complete else "not_met"
    result = {
        "case_id": args.case, "provenance_kind": "synthetic_fixture",
        "diagnostic_fixture": True, "physical_acceptance_claimed": False,
        "maneuver_completed": complete,
        "physical_checks": {"maneuver": {
            "status": status,
            "method": "900-frame synthetic station and final-halt target check",
            "sources": ["synthetic_station_rows_in_probe"],
            "intervals": [{"first": 0, "last": 899}] if rows else [],
        }},
        "realized_observables": {"synthetic_first_station_m": rows[0]["station_m"],
                                 "synthetic_final_station_m": rows[-1]["station_m"],
                                 "synthetic_final_halt_frames": 400} if rows else {},
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"case_id": args.case, "fixture_kind": args.kind,
                      "status": status, "synthetic_rows": len(rows),
                      "physical_acceptance_claimed": False}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
