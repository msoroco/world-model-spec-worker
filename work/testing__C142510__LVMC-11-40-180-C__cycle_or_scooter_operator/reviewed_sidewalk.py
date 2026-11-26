"""Fail-closed custody check for a reviewed original connected sidewalk."""

import hashlib
import json
from pathlib import Path


SOURCE_ROLES = (
    "map_opendrive", "sidewalk_geometry", "connected_route",
    "rider_blueprint", "pedestrian_blueprint", "audible_emitter",
    "pedestrian_microphone",
)


def require(value, message):
    if not value:
        raise ValueError(message)


def load(packet_path, source_root, case_id):
    root = Path(source_root).resolve()
    packet_path = Path(packet_path).resolve()
    require(packet_path.is_relative_to(root) and packet_path.is_file(),
            "reviewed sidewalk packet missing or outside source root")
    packet = json.loads(packet_path.read_text())
    require(packet.get("format") == "c142510-reviewed-sidewalk-v1" and
            packet.get("provenance") == "reviewed_original" and
            packet.get("case_id") == case_id,
            "original reviewed sidewalk packet identity missing")
    sources = packet.get("sources")
    require(isinstance(sources, dict) and set(sources) == set(SOURCE_ROLES),
            "reviewed sidewalk source inventory incomplete")
    site = packet.get("site")
    require(isinstance(site, dict), "reviewed sidewalk site missing")
    for role in SOURCE_ROLES:
        ref = sources[role]
        require(isinstance(ref, dict) and ref.get("path") and ref.get("sha256"),
                "reviewed source reference missing: " + role)
        path = (root / ref["path"]).resolve()
        require(path.is_relative_to(root) and path.is_file() and
                hashlib.sha256(path.read_bytes()).hexdigest() == ref["sha256"],
                "reviewed source bytes missing or changed: " + role)
    require(site.get("map_sha256") == sources["map_opendrive"]["sha256"] and
            site.get("sidewalk_geometry_sha256") ==
            sources["sidewalk_geometry"]["sha256"] and
            site.get("connected_route_sha256") ==
            sources["connected_route"]["sha256"] and
            site.get("rider_blueprint_sha256") == sources["rider_blueprint"]["sha256"] and
            site.get("pedestrian_blueprint_sha256") == sources["pedestrian_blueprint"]["sha256"] and
            site.get("audible_emitter_source_sha256") == sources["audible_emitter"]["sha256"] and
            site.get("microphone_source_sha256") == sources["pedestrian_microphone"]["sha256"],
            "reviewed source digest not bound to site")
    require(site.get("sidewalk_source_citation") and
            site.get("connected_route_citation") and
            packet.get("reviewer") and packet.get("reviewed_at") and
            site.get("physical_surface_kind") == "sidewalk" and
            site.get("sidewalk_connected") is True,
            "connected physical sidewalk source missing")
    geometry_path = (root / sources["sidewalk_geometry"]["path"]).resolve()
    route_path = (root / sources["connected_route"]["path"]).resolve()
    geometry = json.loads(geometry_path.read_text())
    routes = json.loads(route_path.read_text())
    require(geometry.get("sidewalk_id") == site.get("sidewalk_id") and
            geometry.get("polygon_xy_m") == site.get("sidewalk_polygon_xy_m") and
            routes.get("rider_route_xyz_m") == site.get("rider_route_xyz_m") and
            routes.get("pedestrian_route_xyz_m") == site.get("pedestrian_route_xyz_m"),
            "reviewed sidewalk geometry or route differs from cited source")
    return site, hashlib.sha256(packet_path.read_bytes()).hexdigest()
