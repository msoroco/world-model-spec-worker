"""Independently remeasure a saved original Native approach-distance probe."""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

from sight_measurement import ASSIGNMENT, _source


TARGETS = {"distance_below_500ft": 499, "distance_at_500ft": 500,
           "distance_above_500ft": 501}


def audit(attempt: Path, case_id: str) -> dict:
    suffix = case_id.removeprefix(ASSIGNMENT + "__")
    if not case_id.startswith(ASSIGNMENT + "__") or suffix not in TARGETS:
        raise ValueError("unknown exact approach-distance probe")
    attempt = Path(attempt)
    inventory = json.loads((attempt / "inventory.json").read_text())
    if inventory.get("case_id") != case_id:
        raise ValueError("approach-distance probe case identity mismatch")
    ref = inventory.get("approach_probe", {})
    if ref.get("path") != "approach_motion.json":
        raise ValueError("approach-distance packet reference missing")
    path = attempt / ref["path"]
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if digest != ref.get("sha256"):
        raise ValueError("approach-distance packet source hash changed")
    packet = json.loads(path.read_text())
    geometry = _source(attempt, inventory["sources"]["road_geometry"])
    motion = _source(attempt, inventory["sources"]["ego_motion"])["samples"]
    if (packet.get("case_id") != case_id or packet.get("source_kind") != "original_native" or
            packet.get("probe_target_ft") != TARGETS[suffix] or
            packet.get("legal_visibility_judgment") != "unresolved"):
        raise ValueError("approach-distance packet contract changed")
    active = [(row["frame"], row["time_s"]) for row in motion
              if row["turn_active"] is True]
    samples = packet.get("samples", [])
    if len(samples) != len(active) or not active:
        raise ValueError("approach-distance turn frame coverage changed")
    distances = []
    for row, expected in zip(samples, active):
        if (row.get("frame"), row.get("time_s")) != expected or \
                row.get("vehicle_id") != geometry.get("approach_vehicle_id"):
            raise ValueError("approach-distance frame or vehicle identity changed")
        positions = (row.get("ego_position"), row.get("approach_position"))
        if any(not isinstance(pos, dict) or any(
                not isinstance(pos.get(axis), (int, float)) or not math.isfinite(pos[axis])
                for axis in ("x", "y", "z")) for pos in positions):
            raise ValueError("approach-distance original position missing")
        measured = math.dist([positions[0][a] for a in ("x", "y", "z")],
                             [positions[1][a] for a in ("x", "y", "z")])
        if not math.isclose(measured, row.get("measured_distance_m", -1), abs_tol=1e-9):
            raise ValueError("approach-distance saved measurement changed")
        distances.append(measured)
    target_m = TARGETS[suffix] * 0.3048
    if (not math.isclose(distances[0], packet.get("first_turn_distance_m", -1),
                         abs_tol=1e-9) or abs(distances[0] - target_m) > 0.1):
        raise ValueError("approach-distance original probe target not realized")
    return {"format": "c129731-saved-approach-distance-probe-v1",
            "case_id": case_id, "target_ft": TARGETS[suffix],
            "first_turn_distance_m": distances[0], "original_turn_samples": len(distances),
            "source_sha256": digest, "legal_visibility_judgment": "unresolved"}


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", type=Path, required=True)
    parser.add_argument("--case", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("refusing to overwrite saved approach-distance audit")
    result = audit(args.attempt, args.case)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")


if __name__ == "__main__":
    main()
