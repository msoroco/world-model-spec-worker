"""Independently compare two sealed original median-opening attempts.

No requested behavior or authored case label is treated as a measured outcome.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import median_opening

AID = "testing__C125697__NRS-484B-250-1__motor_vehicle_driver"
PAIR = (AID + "__precedence", AID + "__advance")


def _within(root: Path, path: str) -> Path:
    target = (root / path).resolve()
    if not target.is_relative_to(root) or not target.is_file():
        raise ValueError("missing original comparison source: " + path)
    return target


def audit(precedence_root: Path, advance_root: Path) -> dict:
    roots = [Path(precedence_root).resolve(), Path(advance_root).resolve()]
    receipts = []
    scenes = []
    source_hashes = []
    for root, case in zip(roots, PAIR):
        manifest_path = _within(root, "source-manifest.json")
        scene_path = _within(root, "scene.json")
        manifest = json.loads(manifest_path.read_text())
        scene = json.loads(scene_path.read_text())
        if manifest.get("case_id") != case or scene.get("case_id") != case:
            raise ValueError("wrong exact comparison case or order")
        receipt = median_opening.audit_saved_sources(root, manifest, scene)
        receipts.append(receipt)
        scenes.append(scene)
        source_hashes.append({
            "manifest_sha256": hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
            "scene_sha256": hashlib.sha256(scene_path.read_bytes()).hexdigest(),
            "original_sources": receipt["source_sha256"],
        })
    measured = [receipt["observations"] for receipt in receipts]
    comparison = median_opening.audit_comparison(measured[0], measured[1], scenes[0], scenes[1])
    for key in ("highway_identity_source", "public_access_source", "device_inventory_source",
                "ego_blueprint", "other_blueprint"):
        if scenes[0].get(key) != scenes[1].get(key):
            raise ValueError("comparison fixed condition changed: " + key)
    if (source_hashes[0]["original_sources"]["device_inventory"] !=
            source_hashes[1]["original_sources"]["device_inventory"]):
        raise ValueError("comparison fixed device inventory changed")
    comparison["fixed_conditions_checked"].extend([
        "highway_identity_source", "public_access_source", "device_inventory_source",
        "ego_blueprint", "other_blueprint", "device_inventory_sha256",
    ])
    if not measured[0]["ego_waited_until_other_exit"] or measured[1]["ego_waited_until_other_exit"]:
        raise ValueError("measured response does not match selected precedence contrast")
    return {
        "comparison_id": "inoperative_signal_precedence",
        "case_ids": list(PAIR),
        "source_sha256": source_hashes,
        "observations": measured,
        "comparison": comparison,
        "physical_pixels_reviewed": False,
        "legal_applicability": "unresolved",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--precedence-root", required=True, type=Path)
    parser.add_argument("--advance-root", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    receipt = audit(args.precedence_root, args.advance_root)
    args.output.write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps({"comparison_id": receipt["comparison_id"], "source_bound": True}))


if __name__ == "__main__":
    main()
