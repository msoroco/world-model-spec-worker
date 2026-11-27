"""Require original, source-hashed one-way crossing and countdown signal review."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from countdown_crossing import validate_site

ASSIGNMENT = "testing__C150911__NRS-484B-283-1d2__pedestrian"
REQUIRED = {"opendrive", "highway", "crossing", "sidewalk",
    "pedestrian_signal", "pedestrian_route", "exceptions", "cameras"}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_review(packet: str | Path, source_root: str | Path, case_id: str) -> dict:
    packet, source_root = Path(packet).resolve(), Path(source_root).resolve()
    review = json.loads(packet.read_text())
    if (review.get("assignment_id") != ASSIGNMENT or
            review.get("case_id") != case_id or
            review.get("cell_id") != "C150911"):
        raise ValueError("reviewed countdown crossing identity differs")
    provenance = review.get("source_provenance", {})
    if (provenance.get("kind") != "original_reviewed_site" or
            provenance.get("diagnostic_fixture") is not False or
            not provenance.get("reviewer") or not provenance.get("citation")):
        raise ValueError("external original reviewed countdown site provenance required")
    sources = review.get("sources")
    if not isinstance(sources, dict) or not REQUIRED <= set(sources):
        raise ValueError("reviewed countdown source inventory incomplete")
    loaded = {}
    for name in sorted(REQUIRED):
        item = sources[name]
        if not isinstance(item, dict) or not item.get("path") or not item.get("sha256"):
            raise ValueError("reviewed countdown source binding missing: " + name)
        path = (source_root / item["path"]).resolve()
        if (not path.is_relative_to(source_root) or not path.is_file() or
                sha(path) != item["sha256"]):
            raise ValueError("reviewed countdown source path/hash invalid: " + name)
        loaded[name] = path.read_text() if name == "opendrive" else json.loads(path.read_text())
    highway = loaded["highway"]
    crossing = loaded["crossing"]
    signal = loaded["pedestrian_signal"]
    route = loaded["pedestrian_route"]
    if (highway.get("one_way") is not True or
            highway.get("public_vehicular_access") is not True or
            not highway.get("dedicated_to_public_use") or
            not loaded["sidewalk"].get("accessible")):
        raise ValueError("original one-way public highway or sidewalk review missing")
    if (signal.get("official") is not True or
            type(signal.get("actor_id")) is not int or
            signal.get("facing_pedestrian") is not True or
            signal.get("facing_direction") != "both" or
            signal.get("countdown_capability") != "numeric_legible" or
            not {"dont_walk", "wait", "upraised_hand"} <=
                set(signal.get("allowed_forms", []))):
        raise ValueError("official facing flashing numeric countdown signal review required")
    if (not route.get("pedestrian_actor_id") or
            route.get("signal_actor_id") != signal["actor_id"] or
            route.get("crossing_id") != crossing.get("crossing_id")):
        raise ValueError("pedestrian route, crossing and governing signal differ")
    if (set(loaded["exceptions"].get("reviewed_statutes", [])) !=
            {"NRS 484B.287", "NRS 484B.290", "NRS 484B.350"}):
        raise ValueError("referenced exception source review missing")
    if set(loaded["cameras"]) != {"overview", "approach", "reference_corner", "driver_reference"}:
        raise ValueError("four reviewed countdown camera poses required")
    site = {"cell_id": "C150911", "actor": "pedestrian",
        "layout": "one_way_road", "highway_public_vehicular_access": True,
        "signal_facing_pedestrian": True, "signal_facing_direction": "both",
        "highway_polygon_xy": highway.get("polygon_xy"),
        "crossing_routes": crossing.get("routes"),
        "opendrive_source_sha256": sources["opendrive"]["sha256"],
        "highway_source_sha256": sources["highway"]["sha256"],
        "crossing_source_sha256": sources["crossing"]["sha256"],
        "sidewalk_source_sha256": sources["sidewalk"]["sha256"],
        "signal_source_sha256": sources["pedestrian_signal"]["sha256"],
        "signal_facing_source_sha256": sources["pedestrian_signal"]["sha256"],
        "one_way_direction_source_sha256": sources["highway"]["sha256"],
        "exception_context_source_sha256": sources["exceptions"]["sha256"]}
    validate_site(site)
    return {"review": review, "packet_sha256": sha(packet),
        "sources": loaded, "site": site, "source_root": str(source_root)}
