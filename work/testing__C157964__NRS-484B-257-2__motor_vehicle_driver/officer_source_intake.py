"""Check source bindings before the officer exception can enter a Native run.

This checks review provenance and consistency. It does not decide police
authority, legal control, or immediate hazard from a performer blueprint.
"""

import hashlib
import json
from pathlib import Path


def _source(root, binding, label):
    if not isinstance(binding, dict) or set(binding) != {"path", "sha256"}:
        raise ValueError("Missing source binding: " + label)
    path = binding["path"]
    if not isinstance(path, str) or not path or Path(path).is_absolute() or ".." in Path(path).parts:
        raise ValueError("Unsafe source path: " + label)
    target = (root / path).resolve()
    if not target.is_relative_to(root.resolve()) or not target.is_file():
        raise ValueError("Missing source file: " + label)
    if hashlib.sha256(target.read_bytes()).hexdigest() != binding["sha256"]:
        raise ValueError("Changed source file: " + label)
    return target


def validate(root, packet):
    """Return a source inventory only after explicit reviews agree on site ID."""
    root = Path(root).resolve()
    if packet.get("format") != "worker-officer-subsection-2-source-review":
        raise ValueError("Wrong officer source review format")
    site = packet.get("site_id")
    if not isinstance(site, str) or not site:
        raise ValueError("Missing reviewed site identity")
    bindings = packet.get("sources")
    if not isinstance(bindings, dict):
        raise ValueError("Missing officer source inventory")
    required = ("road", "sign_inventory", "officer_authority", "officer_control",
                "other_route", "camera_sight_review")
    paths = {key: _source(root, bindings.get(key), key) for key in required}
    review = packet.get("review")
    if not isinstance(review, dict) or review.get("site_id") != site:
        raise ValueError("Source review site mismatch")
    if review.get("non_through_highway") is not True:
        raise ValueError("Non-through status lacks source review")
    entrances = review.get("entrances")
    if not isinstance(entrances, list) or len(entrances) < 2:
        raise ValueError("Incomplete all-entrance sign review")
    ids = [e.get("entrance_id") for e in entrances if isinstance(e, dict)]
    if len(ids) != len(entrances) or any(not isinstance(i, str) or not i for i in ids) or len(set(ids)) != len(ids):
        raise ValueError("Invalid reviewed entrance identities")
    for entrance in entrances:
        if entrance.get("device") not in ("stop", "yield", "none") or entrance.get("sign_visible") is not True:
            raise ValueError("Incomplete entrance device and sight review")
    ego = review.get("ego_entrance_id")
    other = review.get("other_entrance_id")
    indexed = {e["entrance_id"]: e for e in entrances}
    if ego not in indexed or indexed[ego]["device"] not in ("stop", "yield"):
        raise ValueError("Signed ego entrance not reviewed")
    if other not in indexed or other == ego or indexed[other]["device"] != "none":
        raise ValueError("Non-obligated other entrance not reviewed")
    if review.get("officer_authority_reviewed") is not True:
        raise ValueError("Police authority source review required")
    if review.get("officer_control_reviewed") is not True:
        raise ValueError("Actual officer control source review required")
    if review.get("original_camera_sight_reviewed") is not True:
        raise ValueError("Original camera sight review required")
    return {"format": "worker-officer-subsection-2-source-intake",
            "site_id": site, "source_paths": {key: str(path.relative_to(root)) for key, path in paths.items()},
            "ego_entrance_id": ego, "other_entrance_id": other,
            "legal_exception_judgment": "unresolved",
            "immediate_hazard_judgment": "unresolved"}


def load_and_validate(root, packet_path):
    path = Path(packet_path)
    return validate(root, json.loads(path.read_text()))
