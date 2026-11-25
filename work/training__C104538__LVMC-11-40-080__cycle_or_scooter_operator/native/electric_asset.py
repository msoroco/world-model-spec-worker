"""Fail-closed Native asset check for the two unselected electric rider classes.

This is a construction gate, not proof of statutory classification. The legal
class still requires a reviewed original asset and source pixels.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path

CLASSES = ("electric_bicycle", "electric_scooter")
LEGAL_CLASS_SOURCES = {
    "electric_bicycle": ("NRS-484B-017", "NRS-484A-081"),
    "electric_scooter": ("NRS-484B-018", "NRS-484A-082", "NRS-482-0295"),
}
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


def bind_reviewed_asset(library, machine_class: str, evidence: dict,
                        source_root: Path) -> dict:
    """Require an exact source-hashed review before an electric-class spawn.

    This binds an asset proposal and live inventory only. The recorded rider
    and device pixels still require local review after capture.
    """
    source_root = Path(source_root).resolve()
    if not isinstance(evidence, dict):
        raise ValueError("Electric asset review evidence is required")
    blueprint_id = evidence.get("blueprint_id")
    if machine_class not in LEGAL_CLASS_SOURCES:
        raise ValueError("Unknown electric rider class")
    review = evidence.get("class_review", {})
    if (review.get("legal_sources") != list(LEGAL_CLASS_SOURCES[machine_class]) or
            not review.get("reviewer") or review.get("conclusion") != machine_class):
        raise ValueError("Electric class-specific legal review is required")
    refs = evidence.get("source_refs")
    if not isinstance(refs, list) or not refs:
        raise ValueError("Electric asset review needs exact source references")
    bound = {}
    for ref in refs:
        relative = ref.get("path") if isinstance(ref, dict) else None
        if not isinstance(relative, str) or not relative:
            raise ValueError("Electric asset source path is missing")
        path = (source_root / relative).resolve()
        if path == source_root or source_root not in path.parents or not path.is_file():
            raise ValueError("Electric asset source must exist inside source root")
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if digest != ref.get("sha256") or relative in bound:
            raise ValueError("Electric asset review source changed or duplicated")
        bound[relative] = digest
    selected = validate_blueprint(library, machine_class, blueprint_id, evidence)
    return {**selected, "review_source_sha256": bound,
            "classification_review_record_bound": True,
            "classification_review_pending": True,
            "original_pixel_review_pending": True,
            "legal_verdict_claimed": False}


def spawn_reviewed_electric(world, machine_class: str, evidence: dict,
                           source_root: Path, transform):
    """Spawn only the exactly reviewed live blueprint; retain its Native ID."""
    library = world.get_blueprint_library()
    bound = bind_reviewed_asset(library, machine_class, evidence, source_root)
    blueprint = library.find(bound["blueprint_id"])
    if blueprint.id != bound["blueprint_id"]:
        raise ValueError("Live electric blueprint identity changed")
    actor = world.spawn_actor(blueprint, transform)
    if actor is None or actor.type_id != bound["blueprint_id"]:
        if actor is not None:
            actor.destroy()
        raise ValueError("Spawned electric actor differs from reviewed blueprint")
    return actor, {**bound, "native_actor_id": actor.id,
                   "original_rider_posture_verified": False,
                   "original_class_pixels_verified": False}


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
