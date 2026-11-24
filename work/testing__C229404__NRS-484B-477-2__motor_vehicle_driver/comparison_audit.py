"""Independent CPU audit of original clear/overlap access measurements.

This audits experimental isolation and measured geometry, not legal blocking.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from access_measurement import ASSIGNMENT, measure


FIXED_FIELDS = ("highway_status", "cul_de_sac", "highway_source",
                "alley_classification_source", "cul_de_sac_source",
                "property_id", "property_abutting_source",
                "driveway_ownership_source", "vehicular_use_source",
                "access_kind", "access_corridor_polygon_m", "ego_vehicle_id")


def _geometry(root: Path, inventory: dict) -> dict:
    entry = inventory["sources"]["alley_geometry"]
    rel = Path(entry["path"])
    if rel.is_absolute() or ".." in rel.parts:
        raise ValueError("comparison source path escapes attempt")
    path = (root / rel).resolve()
    if not path.is_relative_to(root.resolve()):
        raise ValueError("comparison source path escapes attempt")
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != entry["sha256"]:
        raise ValueError("comparison original geometry hash mismatch")
    return json.loads(raw)


def audit(clear_root: Path, overlap_root: Path, kind: str) -> dict:
    if kind not in ("driveway", "entrance"):
        raise ValueError("comparison access kind invalid")
    roots = [Path(clear_root), Path(overlap_root)]
    cases = [ASSIGNMENT + "__" + kind + suffix for suffix in ("_clear", "_overlap")]
    inventories = [json.loads((root / "inventory.json").read_text()) for root in roots]
    results = [measure(root, inventory, case)
               for root, inventory, case in zip(roots, inventories, cases)]
    geometries = [_geometry(root, inventory) for root, inventory in zip(roots, inventories)]
    differences = [name for name in FIXED_FIELDS if geometries[0].get(name) != geometries[1].get(name)]
    if differences:
        raise ValueError("comparison fixed alley/access conditions changed: " + ", ".join(differences))
    if results[0]["original_frames"] != results[1]["original_frames"]:
        raise ValueError("comparison recording duration changed")
    clear_area, overlap_area = [row["max_access_intrusion_area_m2"] for row in results]
    if not clear_area < overlap_area:
        raise ValueError("comparison deliberate footprint difference absent")
    return {"format": "c229404-original-access-comparison-v1",
            "comparison_id": kind + "_parking_position", "case_ids": cases,
            "source_sha256": [row["source_sha256"] for row in results],
            "fixed_geometry_fields_checked": list(FIXED_FIELDS),
            "measured_max_intrusion_area_m2": [clear_area, overlap_area],
            "statutory_blocking_judgment": "unresolved"}


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--clear-attempt", type=Path, required=True)
    parser.add_argument("--overlap-attempt", type=Path, required=True)
    parser.add_argument("--kind", choices=("driveway", "entrance"), required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("refusing to overwrite comparison audit")
    result = audit(args.clear_attempt, args.overlap_attempt, args.kind)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")


if __name__ == "__main__":
    main()
