"""Bind fixture claims to separate source bytes before measuring a saved capture."""
import hashlib
import json
from pathlib import Path

ROLES = ("fixture-identity", "fixture-geometry", "sidewalk-geometry",
         "front-orientation")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def reviewed_context(attempt):
    attempt = Path(attempt)
    road = attempt / "road.xodr"
    if not road.is_file():
        raise ValueError("Missing required source: road.xodr")
    inventory_path = attempt / "fixture-inventory.json"
    if not inventory_path.is_file():
        raise ValueError("Missing required source: fixture-inventory.json")
    inventory = json.loads(inventory_path.read_text())
    diagnostic = (attempt / "acquisition-provenance.json").is_file() and json.loads(
        (attempt / "acquisition-provenance.json").read_text()).get(
            "provenance_kind") == "synthetic_fixture"
    if inventory.get("fixture_proxy_blueprint_id") and not diagnostic:
        raise ValueError("Generic fixture proxy cannot establish sidewalk elevator identity")
    hashes = {}
    for role in ROLES:
        name = "fixture-review/" + role
        record_path = attempt / (name + ".json")
        source_path = attempt / (name + ".source.txt")
        if not record_path.is_file() or not source_path.is_file():
            raise ValueError("Missing required source: " + name + ".json")
        record = json.loads(record_path.read_text())
        if record.get("role") != role or record.get("source_sha256") != sha(source_path):
            raise ValueError("Source role hash mismatch: " + role)
        if record.get("provenance_kind") != ("synthetic_fixture" if diagnostic else "original_native_review"):
            raise ValueError("Source role provenance mismatch: " + role)
        if record.get("reviewed") is not True:
            raise ValueError("Source role not reviewed: " + role)
        hashes[role] = sha(record_path)
    identity = json.loads((attempt / "fixture-review/fixture-identity.json").read_text())
    geometry = json.loads((attempt / "fixture-review/fixture-geometry.json").read_text())
    sidewalk = json.loads((attempt / "fixture-review/sidewalk-geometry.json").read_text())
    front = json.loads((attempt / "fixture-review/front-orientation.json").read_text())
    if identity.get("fixture_kind") not in ("sidewalk_elevator", "sidewalk_chute"):
        raise ValueError("Sidewalk elevator or chute identity not sourced")
    if front.get("front_is_road_facing") is not True:
        raise ValueError("Fixture front orientation not sourced")
    if geometry.get("fixture_bounds_m") != inventory.get("fixture_bounds_m") or sidewalk.get(
            "sidewalk_bounds_m") != inventory.get("sidewalk_bounds_m"):
        raise ValueError("Reviewed geometry differs from Native fixture inventory")
    if any(record.get("road_sha256") != sha(road) for record in
           (identity, geometry, sidewalk, front)):
        raise ValueError("Reviewed source map differs from saved Native map")
    return {"source_kind": "native_sidewalk_fixture_and_vehicle_readback",
            "native_map_sha256": sha(road),
            "fixture_identity_sha256": hashes["fixture-identity"],
            "fixture_geometry_sha256": hashes["fixture-geometry"],
            "sidewalk_geometry_sha256": hashes["sidewalk-geometry"],
            "front_orientation_sha256": hashes["front-orientation"],
            "fixture_kind": identity["fixture_kind"],
            "fixture_bounds_m": geometry["fixture_bounds_m"],
            "sidewalk_bounds_m": sidewalk["sidewalk_bounds_m"],
            "diagnostic_fixture": diagnostic}
