"""Fail-closed Native asset check for the two unselected electric rider classes.

This is a construction gate, not proof of statutory classification. The legal
class still requires a reviewed original asset and source pixels.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path

CLASSES = ("electric_bicycle", "electric_scooter")
BICYCLE_BLUEPRINTS = frozenset((
    "vehicle.bh.crossbike", "vehicle.diamondback.century",
    "vehicle.gazelle.omafiets",
))


def validate_blueprint(library, machine_class: str, blueprint_id: str,
                       evidence: dict) -> dict:
    if machine_class not in CLASSES:
        raise ValueError("Unknown electric rider class")
    if not isinstance(blueprint_id, str) or not blueprint_id.startswith("vehicle."):
        raise ValueError("A specific Native vehicle blueprint is required")
    if blueprint_id in BICYCLE_BLUEPRINTS:
        raise ValueError("Ordinary bicycle asset cannot prove an electric class")
    if not isinstance(evidence, dict) or evidence.get("machine_class") != machine_class:
        raise ValueError("Class-specific asset evidence is required")
    if evidence.get("blueprint_id") != blueprint_id:
        raise ValueError("Asset evidence must bind the exact blueprint")
    if evidence.get("source_kind") != "reviewed_native_asset" or not evidence.get("reviewer"):
        raise ValueError("Reviewed Native asset evidence is required")
    matches = [b for b in library.filter(blueprint_id) if b.id == blueprint_id]
    if len(matches) != 1:
        raise ValueError("Exact Native electric asset is unavailable")
    return {"machine_class": machine_class, "blueprint_id": blueprint_id,
            "native_asset_found": True, "classification_review_pending": True}


def local_preflight() -> dict:
    return {"carla_python_available": importlib.util.find_spec("carla") is not None,
            "electric_assets_selected": False,
            "available_bicycle_blueprints": sorted(BICYCLE_BLUEPRINTS),
            "electric_class_inferred_from_bicycle": False,
            "live_blueprint_inventory_checked": False}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = local_preflight()
    if args.output:
        args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    else:
        print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
