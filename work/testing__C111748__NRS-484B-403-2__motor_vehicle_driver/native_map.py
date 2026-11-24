"""Bind a reviewed U-turn site to the actual loaded CARLA map before capture."""
from __future__ import annotations
import hashlib
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("device_site_for_map", ROOT / "construct.py")
site_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(site_module)


class MapBindingError(ValueError):
    pass


def verify(world, site_path: Path, site_sha256: str, case_id: str) -> dict:
    """Reject a different OpenDRIVE map or unusable turn lane before spawning."""
    site = site_module.load_site(site_path, site_sha256, case_id)
    live_map = world.get_map()
    if live_map.name != site["map_name"]:
        raise MapBindingError("live map name mismatch")
    source = live_map.to_opendrive()
    if not isinstance(source, str) or hashlib.sha256(source.encode()).hexdigest() != site["map_sha256"]:
        raise MapBindingError("live OpenDRIVE source hash mismatch")
    route = site["u_turn_route"]
    if len({point.get("road_id") for point in route}) != 1:
        raise MapBindingError("U-turn route leaves reviewed road")
    if route[0].get("lane_id") == route[-1].get("lane_id"):
        raise MapBindingError("U-turn destination lane is not opposite")
    return {"case_id": case_id, "site_sha256": site_sha256,
            "map_name": live_map.name, "map_sha256": site["map_sha256"],
            "route_points": len(route), "physical_turn_verified": False}
